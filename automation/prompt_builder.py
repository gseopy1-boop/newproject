# -*- coding: utf-8 -*-
"""
prompt_builder.py (Single-Account Edition)
- 키워드(3개 권장) + themes.json의 테마 힌트를 섞어 이미지 프롬프트 생성
- 외부 의존성 없음(표준 라이브러리)
- 반환 형태는 down-stream(이미지 생성기)에 친화적인 dict

사용 예:
from automation.prompt_builder import build_image_prompt
p = build_image_prompt(["기억의 파동","빛 신호","도시 리듬"], theme_hint="retro_pc", seed=42)
print(p["prompt"])
"""

from __future__ import annotations
import os
import json
import random
import re
from typing import Any, Dict, List, Optional, Tuple

# ---------- 내부 유틸 ----------

def _repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))          # .../automation
    return os.path.abspath(os.path.join(here, ".."))           # 프로젝트 루트 추정

def _themes_path() -> str:
    # 루트의 themes.json 사용 (없으면 자동 폴백)
    return os.path.join(_repo_root(), "themes.json")

def _safe_open_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _uniq(seq: List[str]) -> List[str]:
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            out.append(x)
            seen.add(x)
    return out

# ---------- 테마 로딩/선택 ----------

_DEFAULT_THEMES: Dict[str, Dict[str, Any]] = {
    "retro_pc": {
        "style": "retro computer, pixel hints, low poly shapes, subtle CRT glow",
        "mood": ["nostalgic", "lofi", "calm"],
        "palette": ["teal", "warm gray", "amber"],
        "composition": ["centered subject", "soft vignette"],
        "neg": ["nsfw", "text watermark", "logo"],
    },
    "minimal_desk": {
        "style": "minimal desk setup, clean layout, soft lighting",
        "mood": ["serene", "aesthetic", "neat"],
        "palette": ["off-white", "charcoal", "sage"],
        "composition": ["top-down", "balanced spacing"],
        "neg": ["busy background", "overcrowded elements"],
    },
    "synthwave_city": {
        "style": "synthwave, neon city, futuristic skyline, glow",
        "mood": ["dreamy", "night drive", "neon"],
        "palette": ["magenta", "cyber blue", "violet"],
        "composition": ["rule of thirds", "wide angle"],
        "neg": ["daylight", "desaturated colors"],
    },
}

def load_themes() -> Dict[str, Dict[str, Any]]:
    data = _safe_open_json(_themes_path())
    if isinstance(data, dict) and data:
        return data
    # 파일이 없거나 잘못됐으면 기본값
    return _DEFAULT_THEMES

def pick_theme(theme_hint: Optional[str], themes: Dict[str, Dict[str, Any]], seed: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
    if seed is not None:
        random.seed(seed)
    keys = list(themes.keys())
    if not keys:
        themes = _DEFAULT_THEMES
        keys = list(themes.keys())

    if theme_hint:
        key = theme_hint.strip().lower()
        if key in themes:
            return key, themes[key]

    # 힌트가 없거나 못 찾으면 랜덤
    key = random.choice(keys)
    return key, themes[key]

# ---------- 문장 구성 ----------

def _linker_sentence(keywords: List[str]) -> str:
    """
    3개 키워드로 감성 문장 한 줄.
    (고급 topic_linker가 없다면 이 간단 버전으로 충분)
    """
    ks = [k for k in [_clean(x) for x in (keywords or [])] if k]
    if len(ks) < 3:
        while len(ks) < 3:
            ks.append("memory")
    k1, k2, k3 = ks[:3]
    return f"{k1}·{k2}·{k3}가 교차하는 장면"

def _english_hint(keywords: List[str]) -> str:
    ks = [k for k in [_clean(x) for x in (keywords or [])] if k]
    if len(ks) < 3:
        while len(ks) < 3:
            ks.append("memory")
    k1, k2, k3 = ks[:3]
    return f"Visualizing {k1}, {k2}, and {k3}."

def _compose_prompt(keywords: List[str], theme: Dict[str, Any]) -> Tuple[str, str]:
    style = theme.get("style", "")
    moods = _uniq(list(map(_clean, theme.get("mood", []))))
    palette = _uniq(list(map(_clean, theme.get("palette", []))))
    comp = _uniq(list(map(_clean, theme.get("composition", []))))

    line1 = _linker_sentence(keywords)
    line2 = _english_hint(keywords)
    mood_line = ", ".join([m for m in moods if m])
    palette_line = ", ".join([p for p in palette if p])
    comp_line = ", ".join([c for c in comp if c])

    # 메인 프롬프트 (텍스트-to-이미지 모델 친화)
    prompt = ", ".join([t for t in [
        line1, line2,
        style,
        f"mood: {mood_line}" if mood_line else "",
        f"palette: {palette_line}" if palette_line else "",
        f"composition: {comp_line}" if comp_line else "",
        "high quality, detailed, cohesive"
    ] if _clean(t)])

    # 네거티브 프롬프트(지원 모델에서만 사용)
    neg = ", ".join(_uniq(list(map(_clean, theme.get("neg", [])))))

    return prompt, neg

# ---------- 퍼블릭 API ----------

def build_image_prompt(
    keywords: List[str],
    theme_hint: Optional[str] = None,
    seed: Optional[int] = None,
    locale: str = "ko",
    extra: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Returns
    -------
    dict: {
      "prompt": str,            # 생성 프롬프트
      "negative": str,          # 네거티브 프롬프트(옵션)
      "theme_key": str,         # 사용된 테마 키
      "style": str,             # 테마 style 필드(raw)
      "mood": List[str],        # 테마 mood 배열(raw)
      "palette": List[str],     # 테마 palette 배열(raw)
      "composition": List[str], # 테마 composition 배열(raw)
      "seed": Optional[int],
      "locale": str
    }
    """
    themes = load_themes()
    theme_key, theme = pick_theme(theme_hint, themes, seed=seed)
    prompt, negative = _compose_prompt(keywords, theme)
    out = {
        "prompt": prompt,
        "negative": negative,
        "theme_key": theme_key,
        "style": theme.get("style", ""),
        "mood": theme.get("mood", []),
        "palette": theme.get("palette", []),
        "composition": theme.get("composition", []),
        "seed": seed,
        "locale": locale,
    }
    if extra:
        out.update(extra)
    return out

# ---------- 모듈 단독 테스트 ----------
if __name__ == "__main__":
    demo = build_image_prompt(
        ["기억의 파동", "빛 신호", "도시 리듬"],
        theme_hint="retro_pc",
        seed=123
    )
    print(json.dumps(demo, ensure_ascii=False, indent=2))
