# app/utils/themes.py
from __future__ import annotations
import json, os, random
from pathlib import Path
from typing import Dict, Any, List, Tuple

class ThemeNotFound(Exception):
    pass

def load_themes(path: str | None = None) -> List[Dict[str, Any]]:
    p = Path(path or "themes.json")
    if not p.exists():
        raise FileNotFoundError("themes.json not found at project root")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def _weighted_choice(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    weights = [max(1, int(it.get("weight", 1))) for it in items]
    return random.choices(items, weights=weights, k=1)[0]

def pick_theme(theme_id: str | None = None) -> Dict[str, Any]:
    """
    theme_id 가 None 또는 'auto'면 가중 랜덤에서 하나 선택.
    특정 id가 주어지면 해당 테마를 반환 (없으면 예외).
    """
    theme_id = (theme_id or os.getenv("THEME") or "auto").strip().lower()
    data = load_themes()

    if theme_id in ("", "auto", "random"):
        return _weighted_choice(data)

    for it in data:
        if it.get("id", "").lower() == theme_id:
            return it
    raise ThemeNotFound(f"theme '{theme_id}' not found in themes.json")

def theme_to_prompt_hint(theme: Dict[str, Any]) -> str:
    """
    이미지 생성기에 넣을 짧은 힌트 문자열 생성
    예: "mood: nostalgic,cozy; colors: teal,beige; style: pixelated,crt_glow"
    """
    mood = ",".join(theme.get("mood", [])[:2]) or ""
    color = ",".join(theme.get("color", [])[:3]) or ""
    style = ",".join(theme.get("style", [])[:3]) or ""
    parts = []
    if mood:  parts.append(f"mood: {mood}")
    if color: parts.append(f"colors: {color}")
    if style: parts.append(f"style: {style}")
    return "; ".join(parts)
