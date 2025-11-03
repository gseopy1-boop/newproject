# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from app.media.frame95 import apply_win95_frame
from typing import Optional, TYPE_CHECKING

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except Exception:
    Image = None

if TYPE_CHECKING:
    from PIL import Image as PILImage

def _safe_open(path: Optional[str]) -> Optional["PILImage.Image"]:
    if not path or not Image:
        return None
    try:
        im = Image.open(path)
        im.load()
        return im  # type: ignore[return-value]
    except Exception:
        return None

def generate_image_with_reference(
    prompt: str,
    reference_img_path: Optional[str] = None,
    **kwargs,
):
    """
    Win95 스타일 프레임을 생성하고, 참조 이미지가 있으면 내부에 삽입합니다.
    참조 이미지가 없으면 800x800 크기의 빈 흰색 이미지를 콘텐츠로 사용합니다.
    """
    if Image is None:
        return None

    # --- 콘텐츠 로드 (없으면 빈 이미지 생성) ---
    content = _safe_open(reference_img_path)
    if not content:
        content = Image.new("RGB", (800, 800), (255, 255, 255))

    # --- 프레임 설정값 로드 ---
    # kwargs 우선, 없으면 환경변수, 그것도 없으면 기본값
    title = kwargs.get("title", os.getenv("FRAME_TITLE", prompt or "startdesk"))
    footer = kwargs.get("footer", os.getenv("FOOTER_TEXT", "fromstartdesk"))
    theme = kwargs.get("theme", os.getenv("FRAME_THEME", "teal"))

    # --- 프레임 적용 ---
    framed_image = apply_win95_frame(
        content,
        title=title,
        footer=footer,
        theme=theme,
    )

    return framed_image
