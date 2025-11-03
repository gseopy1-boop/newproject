# app/nlp/text_clean.py
import re

def dedup_words_ko(text: str) -> str:
    """
    간단 중복 단어 제거: 같은 단어가 바로 두 번 연속 나오면 한 번만 남김.
    예) '감성 감성으로 본 오늘' -> '감성으로 본 오늘'
    """
    # 공백 기준 토큰화 후 연속 중복 제거
    tokens = text.split()
    deduped = []
    prev = None
    for t in tokens:
        if t != prev:
            deduped.append(t)
        prev = t
    return " ".join(deduped)

def clean_caption(caption: str) -> str:
    # 연속 공백 정리
    caption = re.sub(r"\s+", " ", caption).strip()
    # 단순 연속 중복 제거
    caption = dedup_words_ko(caption)
    return caption
