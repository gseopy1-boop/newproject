# app/nlp/topic_linker.py
from __future__ import annotations
from typing import List, Tuple

# 아주 가벼운 규칙: 키워드 3개만 뽑고, 로케일별 한줄 설명 생성 + 무드 추정
MOOD_BY_KEYWORD = {
    "retro": "nostalgic",
    "pc": "nostalgic",
    "desk": "calm",
    "autumn": "warm",
    "fall": "warm",
    "neon": "vivid",
    "city": "urban",
    "beach": "relaxed",
    "cat": "cozy",
    "fashion": "trendy",
    "iphone": "clean",
    "travel": "adventurous",
}

def _infer_mood(kws: List[str], default="calm") -> str:
    for k in kws:
        t = str(k).lower()
        for key, mood in MOOD_BY_KEYWORD.items():
            if key in t:
                return mood
    return default

def _explain_locale(k3: List[str], locale: str, mood: str) -> str:
    a, b, c = (k3 + ["", "", ""])[:3]
    loc = (locale or "en").lower()
    if loc.startswith("ko"):
        return f"({a}·{b}·{c}를 {mood} 무드로 잇는 구도)"
    if loc.startswith("ja"):
        return f"({a}・{b}・{c} を {mood} ムードで結ぶコンポジション)"
    return f"(Linking {a}, {b}, {c} in a {mood} mood composition)"

def link_keywords(keywords: List[str], locale: str = "en") -> Tuple[List[str], str, str]:
    """
    returns: (k3, explanation, mood)
      - k3: 사용할 3키워드
      - explanation: 로케일별 한줄 설명(캡션 뒤에 덧붙이기 용)
      - mood: 추정 무드 (prompt/caption에 넘길 수 있음)
    """
    k3 = [k for k in (keywords or []) if k][:3]
    mood = _infer_mood(k3)
    expl = _explain_locale(k3, locale, mood)
    return k3, expl, mood
