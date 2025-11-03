# /newproject/automation/trends.py
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Optional, Tuple

# ── 간단 로거 (콘솔 + 파일)
def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _log_path() -> Path:
    log_dir = Path("output/logs")
    _ensure_dir(log_dir)
    return log_dir / "trends.log"

_LOG_FILE = _log_path()

def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [trends] {msg}"
    print(line)
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── 설정
@dataclass
class TrendConfig:
    cache_ttl_days: int = 2
    sleep_min: float = 2.0
    sleep_max: float = 5.0
    batch_size: int = 5
    region_default: str = "KR"
    backfill_days: int = 7
    allow_defaults: bool = True  # 실패 시 기본단어 허용
    use_naver_backup: bool = True
    naver_seed: str = "가,나,다,라,마,바,사,아,자,차,카,타,파,하,AI,뉴스,날씨,음악,게임,영화,드라마,쇼핑,핫딜"

    @staticmethod
    def from_env() -> "TrendConfig":
        def _f(name: str, default: float) -> float:
            try:
                return float(os.getenv(name, str(default)))
            except Exception:
                return default

        def _i(name: str, default: int) -> int:
            try:
                return int(os.getenv(name, str(default)))
            except Exception:
                return default

        def _b(name: str, default: bool) -> bool:
            v = os.getenv(name)
            if v is None:
                return default
            return v.strip().lower() in {"1","true","yes","y","on"}

        return TrendConfig(
            cache_ttl_days=_i("TRENDS_CACHE_TTL_DAYS", 2),
            sleep_min=_f("PYTRENDS_REQUEST_SLEEP_MIN", 2.0),
            sleep_max=_f("PYTRENDS_REQUEST_SLEEP_MAX", 5.0),
            batch_size=_i("PYTRENDS_BATCH_SIZE", 5),
            region_default=os.getenv("TRENDS_REGION_DEFAULT", "KR"),
            backfill_days=_i("TRENDS_BACKFILL_DAYS", 7),
            allow_defaults=_b("TRENDS_ALLOW_DEFAULTS", True),
            use_naver_backup=_b("TRENDS_NAVER_BACKUP", True),
            naver_seed=os.getenv("TRENDS_NAVER_SEED", "가,나,다,라,마,바,사,아,자,차,카,타,파,하,AI,뉴스,날씨,음악,게임,영화,드라마,쇼핑,핫딜"),
        )

# ── 클라이언트
class TrendClient:
    """
    Google Trends 429 하드닝 + 캐시 + Naver 백업 + 백필 + 기본어 래퍼.
    - 캐시: output/logs/cache/trends_YYYY-MM-DD.json
    - TTL: TRENDS_CACHE_TTL_DAYS (일)
    - 429: 지수형 백오프 + 지터, 최대 5회
    - Google 실패 → Naver 제안 API(비공식) 백업 → 실패 시 Backfill → Defaults
    """
    def __init__(self, cfg: Optional[TrendConfig] = None):
        self.cfg = cfg or TrendConfig.from_env()
        self.cache_dir = Path("output/logs/cache")
        _ensure_dir(self.cache_dir)

        self.http_proxy = os.getenv("HTTP_PROXY")
        self.https_proxy = os.getenv("HTTPS_PROXY")

        self._pytrends_ok = False
        try:
            from pytrends.request import TrendReq  # type: ignore
            self.TrendReq = TrendReq
            self._pytrends_ok = True
        except Exception as e:
            _log(f"pytrends import 실패: {e}. Google 수집은 비활성화됩니다.")

    # Public
    def get_daily_keywords(
        self,
        date: Optional[datetime] = None,
        region: Optional[str] = None,
        limit: int = 20,
    ) -> List[str]:
        target_date = (date or datetime.now()).date()
        region = (region or self.cfg.region_default).upper()

        # 1) 캐시 확인
        cached, why = self._read_cache_if_fresh(target_date)
        if cached is not None and len(cached) > 0:
            _log(f"CACHE HIT ({why}): {target_date.isoformat()} / {len(cached)} items")
            return cached[:limit]

        # 2) Google 원천 수집
        items = self._fetch_with_retry(region=region, limit=limit)
        if items:
            self._write_cache(target_date, items)
            return items[:limit]

        # 3) Naver 백업 (옵션)
        if self.cfg.use_naver_backup:
            naver_items = self._fetch_from_naver_backup(limit=limit)
            if naver_items:
                _log(f"NAVER BACKUP OK: {len(naver_items)} items")
                self._write_cache(target_date, naver_items)
                return naver_items[:limit]
            else:
                _log("NAVER BACKUP EMPTY")

        # 4) 백필(backfill) - 최근 n일 캐시에서 가져오기
        backfilled = self._backfill_from_recent_cache(limit=limit)
        if backfilled:
            _log(f"BACKFILL HIT: {len(backfilled)} items")
            self._write_cache(target_date, backfilled)
            return backfilled[:limit]

        # 5) 기본 단어(defaults) - 파이프라인 유지를 위해
        if self.cfg.allow_defaults:
            defaults = self._default_keywords(region, limit=limit)
            _log(f"DEFAULTS USED: {len(defaults)} items")
            self._write_cache(target_date, defaults)
            return defaults[:limit]

        _log("RESULT EMPTY: 모든 시도 실패 (defaults 비활성화).")
        self._write_cache(target_date, [])
        return []

    # Cache
    def _cache_path(self, d: date) -> Path:
        return self.cache_dir / f"trends_{d.isoformat()}.json"

    def _read_cache_if_fresh(self, d: date) -> Tuple[Optional[List[str]], str]:
        p = self._cache_path(d)
        if not p.exists():
            return None, "miss: no file"
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            if datetime.now() - mtime <= timedelta(days=self.cfg.cache_ttl_days):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return [str(x) for x in data], "fresh"
                return None, "miss: invalid format"
            return None, "miss: stale"
        except Exception as e:
            _log(f"캐시 읽기 실패: {e}")
            return None, "miss: error"

    def _write_cache(self, d: date, keywords: List[str]) -> None:
        p = self._cache_path(d)
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(keywords, f, ensure_ascii=False, indent=2)
            _log(f"CACHE WRITE: {p} ({len(keywords)} items)")
        except Exception as e:
            _log(f"캐시 쓰기 실패: {e}")

    # Google fetch with retry (+ pn 후보 순회)
    def _fetch_with_retry(self, region: str, limit: int) -> List[str]:
        if not self._pytrends_ok:
            _log("pytrends 미사용 상태. Google 수집을 건너뜁니다.")
            return []

        proxies = None
        if self.http_proxy or self.https_proxy:
            proxies = {
                "http": self.http_proxy,
                "https": self.https_proxy or self.http_proxy,
            }

        attempt = 0
        base_sleep = max(self.cfg.sleep_min, 1.0)

        pn_candidates = self._pn_candidates(region)
        _log(f"PN candidates: {pn_candidates}")

        while attempt < 5:
            attempt += 1
            try:
                tr = self.TrendReq(hl="ko-KR", tz=540, timeout=(10, 25), proxies=proxies)
                items: List[str] = []
                # pn 후보들을 차례로 시도
                for pn in pn_candidates:
                    try:
                        df = tr.trending_searches(pn=pn)
                    except Exception as e_in:
                        _log(f"inner pn fetch error ({pn}): {e_in}")
                        continue
                    if df is None or getattr(df, "empty", False):
                        _log(f"FETCH EMPTY for pn={pn}")
                        continue
                    local: List[str] = []
                    for _, row in df.iterrows():
                        v = row[0]
                        if isinstance(v, str):
                            local.append(v.strip())
                    if local:
                        items = local
                        _log(f"FETCH OK pn={pn}: {len(items)} items")
                        break
                if items:
                    return items[:limit]
                raise RuntimeError("no pn candidate produced items")
            except Exception as e:
                if attempt >= 5:
                    _log(f"FETCH FAIL (give up): {e}")
                    return []
                sleep_s = base_sleep * (2 ** (attempt - 1))
                jitter = random.uniform(0, 2.0)
                gap = min(max(sleep_s + jitter, self.cfg.sleep_min), self.cfg.sleep_max * 4)
                _log(f"FETCH RETRY {attempt}/5 after {gap:.2f}s (err: {e})")
                time.sleep(gap)

    @staticmethod
    def _pn_candidates(region: str) -> List[str]:
        r = region.upper()
        base = {
            "KR": ["south-korea", "south_korea", "korea"],
            "US": ["united-states", "united_states", "united states", "usa"],
            "JP": ["japan"],
            "GB": ["united-kingdom", "united_kingdom", "united kingdom"],
            "DE": ["germany"],
            "FR": ["france"],
            "IN": ["india"],
            "BR": ["brazil"],
            "CA": ["canada"],
            "AU": ["australia"],
        }
        candidates = base.get(r, ["south-korea"])
        if "worldwide" not in candidates:
            candidates.append("worldwide")
        seen = set()
        uniq = []
        for x in candidates:
            if x not in seen:
                uniq.append(x); seen.add(x)
        return uniq

    # ── NAVER 백업 (제안 API 기반 Heuristic)
    def _fetch_from_naver_backup(self, limit: int) -> List[str]:
        """
        네이버 자동완성(제안) API를 여러 seed로 호출해 상위 질의어를 수집.
        - 비공식 공개 endpoint: ac.search.naver.com (변경 가능성 있음)
        - 인증 불필요
        - 중복 제거 후 상위 N개 반환
        """
        try:
            import requests  # 가벼운 의존성
        except Exception as e:
            _log(f"NAVER BACKUP 불가 (requests 미설치): {e}")
            return []

        seeds = [s.strip() for s in self.cfg.naver_seed.split(",") if s.strip()]
        rng = random.Random(int(datetime.now().strftime("%Y%m%d")))
        rng.shuffle(seeds)

        collected: List[str] = []
        seen = set()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }

        # 비공식 제안 API 패턴
        # https://ac.search.naver.com/nx/ac?q=<query>&st=100&r_format=json&r_enc=utf-8
        # 응답 예: {"items":[[["연관어1",...], ...]]} 형태(버전에 따라 다름)
        def _suggest(q: str) -> List[str]:
            try:
                url = "https://ac.search.naver.com/nx/ac"
                params = {
                    "q": q,
                    "st": "100",
                    "r_format": "json",
                    "r_enc": "utf-8",
                    "q_enc": "utf-8",
                    "t_koreng": "1",
                }
                resp = requests.get(url, params=params, headers=headers, timeout=5)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                items = data.get("items") or []
                results: List[str] = []
                # 구조 방어적으로 파싱
                for block in items:
                    if not isinstance(block, list):
                        continue
                    for sub in block:
                        if not isinstance(sub, list) or not sub:
                            continue
                        cand = sub[0]
                        if isinstance(cand, str) and cand.strip():
                            results.append(cand.strip())
                return results
            except Exception:
                return []

        for seed in seeds[:30]:  # 과한 호출 방지
            sugg = _suggest(seed)
            if not sugg:
                continue
            # 후보에서 의미 없는 단어/기호 제거 & 길이 필터
            for s in sugg:
                s2 = s.strip()
                if len(s2) < 2:
                    continue
                if s2 in seen:
                    continue
                seen.add(s2)
                collected.append(s2)
                if len(collected) >= limit * 2:
                    break
            if len(collected) >= limit * 2:
                break

        # 단순 정렬: 길이/한글 우선 힌트(가벼운 휴리스틱)
        def _score(w: str) -> tuple:
            # 한글 비중, 길이, a~z 여부 등으로 대략 랭킹
            hangul = sum(1 for ch in w if '가' <= ch <= '힣')
            latin = sum(1 for ch in w if 'a' <= ch.lower() <= 'z')
            return (-hangul, len(w), latin)

        uniq_sorted = sorted(collected, key=_score)
        return uniq_sorted[:limit]

    # 최근 n일 캐시에서 채워넣기
    def _backfill_from_recent_cache(self, limit: int) -> List[str]:
        for i in range(1, max(1, self.cfg.backfill_days) + 1):
            d = (datetime.now() - timedelta(days=i)).date()
            p = self._cache_path(d)
            if not p.exists():
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    _log(f"BACKFILL from {p.name}: {len(data)} items")
                    return [str(x) for x in data][:limit]
            except Exception as e:
                _log(f"BACKFILL read error: {e}")
        return []

    # 기본 단어(최후의 안전장치)
    @staticmethod
    def _default_keywords(region: str, limit: int = 20) -> List[str]:
        base = [
            "Windows 95", "레트로", "픽셀아트", "디지털 아트", "AI 이미지",
            "미니멀 디자인", "테크 뉴스", "개발자 팁", "트렌드", "인스타그램",
            "콘텐츠 제작", "오토메이션", "프롬프트", "캡션", "해시태그",
            "스타트데스크", "fromstartdesk", "갤러리", "툴킷", "워크플로우",
            "클라우드", "파이썬", "Next.js", "Supabase", "오픈소스",
        ]
        seed = int(datetime.now().strftime("%Y%m%d")) ^ sum(map(ord, region))
        rng = random.Random(seed)
        rng.shuffle(base)
        return base[:max(5, limit)]

# ── 함수형 어댑터 (기존 코드 호환)
def get_daily_keywords(date: Optional[datetime] = None,
                       region: Optional[str] = None,
                       limit: int = 20) -> List[str]:
    return TrendClient().get_daily_keywords(date=date, region=region, limit=limit)

# ── 모듈 단독 실행 테스트
if __name__ == "__main__":
    keys = get_daily_keywords(limit=20)
    _log(f"DEMO → {keys[:5]}")
    print(keys)
