# -*- coding: utf-8 -*-
"""
caption_builder.py (Single-Account Edition)
------------------------------------------------
단일 계정(메인 계정) 전략에 맞춘 캡션/해시태그 생성기.

핵심 특징:
- PROFILE=main 기준으로 동작 (다계정 분기 제거)
- 한글 메인 라인 + 짧은 영어 태그라인 혼합
- 테마 힌트(theme_hint)와 키워드 기반 해시태그 자동 생성
- 인스타 규칙 고려: 2,200자 내, 해시태그 30개 이하
- 중복 제거, 불용기호 정리, 과도한 길이/개수 자동 트림
- 시드 고정(seed) 지원 → 재현 가능한 랜덤 선택

외부 의존성: 없음 (표준 라이브러리만 사용)
"""

from __future__ import annotations
import os
import re
import random
import unicodedata
from typing import List, Dict, Optional, Tuple


# ===== 설정 =====
MAX_CAPTION_LEN = 2200
MAX_HASHTAGS = 30               # 인스타그램 권장 상한
TARGET_HASHTAG_RANGE = (18, 26) # 생성 목표 범위(상황에 따라 트림)

# 테마별 기본 해시태그/무드 이모지
THEME_PRESETS: Dict[str, Dict[str, List[str]]] = {
    "retro_pc": {
        "tags": ["#retro", "#vintage", "#pixelart", "#lofi", "#nostalgia"],
        "emojis": ["🕹️", "💾", "📟", "🧷"],
    },
    "minimal_desk": {
        "tags": ["#minimal", "#clean", "#workspace", "#aesthetic", "#calm"],
        "emojis": ["🧘", "📐", "🗂️", "✨"],
    },
    "synthwave_city": {
        "tags": ["#synthwave", "#neon", "#vaporwave", "#citylights", "#futuristic"],
        "emojis": ["🌆", "💿", "🌃", "🔮"],
    },
    # 확장: themes.json 을 읽어 주입하는 쪽에서 theme_hint만 맞춰 전달하면 됨.
}

# 공통 베이스 해시태그(브랜드/전략 관점)
BASE_TAGS = [
    "#art", "#aiart", "#creative", "#daily", "#trend", "#design",
    "#digitalart", "#abstract", "#aivisual", "#generative",
    "#inspiration", "#mood", "#color", "#shapes", "#pattern",
]

# 키워드→태그 변환 시 제외할 토큰
STOPWORDS = set(["the", "and", "of", "to", "in", "for", "on", "with", "at", "a", "an", "is", "are"])


# ===== 유틸 =====
def _clean_keyword(s: str) -> str:
    # 양쪽 공백 제거 + 공백 압축
    return re.sub(r"\s+", " ", (s or "").strip())

def _normalize_hashtag_token(s: str) -> str:
    """
    해시태그 토큰 정규화:
    - 앞뒤 공백 제거
    - 특수문자/이모지 제거(해시태그 허용 범위만 남김: 한글/영문/숫자/언더스코어)
    - 공백/하이픈 → 언더스코어
    """
    s = _clean_keyword(s)
    s = s.replace("-", "_").replace(" ", "_")
    # 허용: 한글, 영문, 숫자, 언더스코어
    s = re.sub(r"[^\w\u3131-\u318E\uAC00-\uD7A3]", "", s, flags=re.UNICODE)
    return s

def _ascii_fallback(s: str) -> str:
    """
    비ASCII를 제거한 ASCII 대체 태그(가끔 국제 노출 대비).
    """
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    ascii_only = re.sub(r"[^A-Za-z0-9_]", "", ascii_only)
    return ascii_only

def _uniq(seq: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


# ===== 해시태그 빌더 =====
def _keywords_to_tags(keywords: List[str]) -> List[str]:
    tags: List[str] = []
    for kw in keywords:
        kw = _clean_keyword(kw)
        if not kw:
            continue
        # 공백 단위로 토큰화 → stopword 제외
        tokens = [t for t in re.split(r"[\s/|,]+", kw) if t]
        tokens = [t for t in tokens if t.lower() not in STOPWORDS]
        # 전체 키워드 자체도 태그로 시도
        cand = [kw] + tokens
        for c in cand:
            token = _normalize_hashtag_token(c)
            if token:
                tags.append("#" + token)

                # 한국어 키워드의 ASCII 대체 태그도 1개 정도만 추가
                fallback = _ascii_fallback(token)
                if fallback and fallback.lower() != token.lower():
                    tags.append("#" + fallback.lower())
    return tags

def _theme_tags(theme_hint: Optional[str]) -> Tuple[List[str], List[str]]:
    """
    테마 힌트에서 프리셋 태그/이모지 목록을 반환.
    """
    if not theme_hint:
        return [], []
    key = (theme_hint or "").strip().lower()
    preset = THEME_PRESETS.get(key, None)
    if not preset:
        return [], []
    return preset.get("tags", []), preset.get("emojis", [])


def build_hashtags(
    keywords: List[str],
    theme_hint: Optional[str] = None,
    seed: Optional[int] = None,
    target_range: Tuple[int, int] = TARGET_HASHTAG_RANGE,
    max_len: int = MAX_HASHTAGS
) -> List[str]:
    """
    키워드 + 테마 기반 해시태그 목록 생성.
    - BASE_TAGS + THEME_PRESETS + 키워드 태그
    - 중복 제거 후 무작위 섞기
    - 개수 트림 (target_range ~ max_len)
    """
    if seed is not None:
        random.seed(seed)

    theme_base, _ = _theme_tags(theme_hint)
    kw_tags = _keywords_to_tags(keywords)

    pool = _uniq(BASE_TAGS + theme_base + kw_tags)

    # 길이/가독성을 위해 너무 긴 토큰 제외 (예: 40자 초과)
    pool = [t for t in pool if len(t) <= 40]

    # 랜덤 셔플
    random.shuffle(pool)

    # 목표 범위 안에서 추출(풀이 적으면 있는 만큼)
    lo, hi = target_range
    take = min(max_len, max(lo, min(hi, len(pool))))
    return pool[:take]


# ===== 캡션 빌더 =====
def _compose_lines(
    keywords: List[str],
    theme_hint: Optional[str],
    emojis: List[str]
) -> Tuple[str, str, str]:
    """
    본문 3줄 구성:
    1) KR 메인: "A·B·C의 흐름"
    2) EN 보조: "Exploring A, B, and C."
    3) 무드 라인: (이모지 + 테마명)
    """
    ks = [k for k in [_clean_keyword(x) for x in (keywords or [])] if k]
    if len(ks) < 3:
        # 3개 미만인 경우 안전하게 채움
        while len(ks) < 3:
            ks.append("memory")

    k1, k2, k3 = ks[:3]

    line_kr = f"{k1}·{k2}·{k3}의 흐름"
    line_en = f"Exploring {k1}, {k2}, and {k3}."
    theme_label = (theme_hint or "mood").replace("_", " ")
    em = " ".join(emojis[:2]) if emojis else ""
    line_mood = f"{em} {theme_label}".strip()

    return line_kr, line_en, line_mood


def build_caption(
    keywords: List[str],
    theme_hint: Optional[str] = None,
    extra_lines: Optional[List[str]] = None,
    seed: Optional[int] = None,
    hashtag_only: bool = False,
) -> str:
    """
    최종 캡션 문자열 생성.

    Parameters
    ----------
    keywords : List[str]
        트렌드에서 고른 3개 키워드 권장 (부족해도 처리됨)
    theme_hint : Optional[str]
        retro_pc / minimal_desk / synthwave_city ... 등
    extra_lines : Optional[List[str]]
        마지막에 추가로 붙일 커스텀 라인들
    seed : Optional[int]
        랜덤 시드(재현성)
    hashtag_only : bool
        True이면 해시태그 블록만 반환(디버그/실험용)
    """
    if seed is not None:
        random.seed(seed)

    # 테마 이모지
    _, theme_emojis = _theme_tags(theme_hint)

    # 본문 3줄
    line_kr, line_en, line_mood = _compose_lines(keywords, theme_hint, theme_emojis)

    # 해시태그
    tags = build_hashtags(keywords, theme_hint=theme_hint, seed=seed)
    tag_block = " ".join(tags)

    if hashtag_only:
        return tag_block

    # 본문 조립
    parts: List[str] = [line_kr, line_en]
    if line_mood:
        parts.append(line_mood)

    if extra_lines:
        parts.extend([_clean_keyword(x) for x in extra_lines if _clean_keyword(x)])

    # 본문+해시태그 두 단락으로 구성
    body = "\n".join([p for p in parts if p])
    caption = f"{body}\n\n{tag_block}".strip()

    # 길이 초과 시 해시태그부터 점진적으로 트림
    if len(caption) > MAX_CAPTION_LEN:
        # 해시태그를 줄여가며 제한 만족
        tag_list = tag_block.split()
        while len(caption) > MAX_CAPTION_LEN and tag_list:
            tag_list.pop()  # 끝에서 제거
            tag_block = " ".join(tag_list)
            caption = f"{body}\n\n{tag_block}".strip()

        # 그래도 넘치면 본문을 살짝 줄임(영문 라인 우선)
        if len(caption) > MAX_CAPTION_LEN:
            # 영어 라인부터 축약
            short_en = re.sub(r"[^\w\s,\.!?\-]", "", line_en)
            if len(short_en) > 60:
                short_en = short_en[:57] + "..."
            parts2 = [line_kr, short_en]
            if line_mood:
                parts2.append(line_mood)
            if extra_lines:
                parts2.extend(extra_lines)
            body = "\n".join([p for p in parts2 if p])
            caption = f"{body}\n\n{tag_block}".strip()

    return caption


# ===== 모듈 자체 테스트 =====
if __name__ == "__main__":
    os.environ["PROFILE"] = os.getenv("PROFILE", "main")
    sample_keywords = ["기억의 파동", "빛 신호", "도시 리듬"]
    demo = build_caption(
        sample_keywords,
        theme_hint="retro_pc",
        extra_lines=None,
        seed=42
    )
    print(demo)
