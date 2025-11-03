# app/nlp/prompt_gen.py
from __future__ import annotations
import re

# ---- 기본 로케일별 베이스 해시태그(가벼운 코어 세트) ----
BASE_TAGS = {
    "ko": ["오늘의사진", "일상기록", "분위기", "감성사진", "디지털아트", "레트로", "무드", "컬러", "트렌드", "아트"],
    "en": ["dailysnap", "aesthetic", "mood", "digitalart", "retro", "color", "trend", "art", "inspiration", "style"],
    "ja": ["今日の一枚", "日常記録", "雰囲気", "デジタルアート", "レトロ", "ムード", "カラー", "トレンド", "アート", "インスピレーション"],
}

def _pick3(keywords: list[str]) -> list[str]:
    # 키워드가 3개 미만이면 가능한 만큼만 사용
    return [kw for kw in keywords[:3] if kw and kw.strip()]

def _norm_hashtag_token(s: str) -> str:
    # 공백/특수문자 제거: 해시태그 토큰으로 안전화
    token = re.sub(r"[^A-Za-z0-9가-힣ぁ-ゖァ-ヺｦ-ﾟ一-龥ー・･_]", "", s.replace(" ", ""))
    return token[:30]  # 너무 길면 컷

def _caption_template(key3: list[str], locale: str, mood: str = "calm") -> str:
    a, b, c = (key3 + ["", "", ""])[:3]

    if locale == "ko":
        # 2문장 템플릿
        return f"{a}, {b}, {c} — 이 세 가지 결로 한 장면을 만들었어요. 오늘의 무드: {mood}."
    if locale == "ja":
        return f"{a}, {b}, {c} — 3つのキーワードで1枚のシーンに。今日のムード：{mood}。"
    # default: en
    return f"{a}, {b}, {c} — merged into one scene. Today's mood: {mood}."

def _locale_key(locale: str) -> str:
    loc = (locale or "en").lower()
    if loc.startswith("ko"):
        return "ko"
    if loc.startswith("ja"):
        return "ja"
    return "en"

def build_caption_and_tags(
    keywords: list[str],
    locale: str = "en",
    mood: str | None = None,
) -> tuple[str, list[str]]:
    """
    입력: keywords(최대 3개 사용), locale: 'ko'|'en'|'ja'
    출력: caption(str), hashtags(list[str], '#' 포함, 8~12개 내)
    """
    loc = _locale_key(locale)
    key3 = _pick3(keywords)
    mood = mood or {"ko": "차분함", "ja": "落ち着き", "en": "calm"}[loc]

    caption = _caption_template(key3, loc, mood=mood)

    # 키워드 기반 해시태그 (우선 순위 높음)
    kw_tags = []
    for kw in key3:
        t = _norm_hashtag_token(kw)
        if t:
            kw_tags.append(t)

    # 로케일 기본 태그에서 보충
    base = BASE_TAGS.get(loc, BASE_TAGS["en"])

    # 최종 해시태그 리스트 구성 (중복 제거, 10개 내외)
    seen = set()
    merged = []
    for t in kw_tags + base:
        tok = _norm_hashtag_token(t)
        if not tok or tok in seen:
            continue
        seen.add(tok)
        merged.append("#" + tok)
        if len(merged) >= 12:
            break

    # 최소 8개는 채우기 (부족하면 base 반복)
    i = 0
    while len(merged) < 8 and i < len(base):
        tok = _norm_hashtag_token(base[i])
        i += 1
        if tok and ("#" + tok) not in merged:
            merged.append("#" + tok)

    return caption, merged
