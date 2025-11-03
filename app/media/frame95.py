# /newproject/app/media/frame95.py
from __future__ import annotations
from typing import Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
import os, re

# ── env helpers ─────────────────────────────────────────────────────────
def _env_str(k: str, d: str) -> str:
    v = os.getenv(k);  return v if v and v.strip() != "" else d
def _env_bool(k: str, d: bool) -> bool:
    v = os.getenv(k);  return d if v is None else v.strip().lower() in {"1","true","yes","y","on"}
def _env_int(k: str, d: int) -> int:
    v = os.getenv(k);  s = ("" if v is None else v.strip())
    if s == "": return d
    try: return int(s)
    except:
        try: return int(float(s))
        except:
            m = re.search(r"\d+", s);  return int(m.group(0)) if m else d

# ── palette ─────────────────────────────────────────────────────────────
def _pal(kawaii: bool):
    if kawaii:
        return {
            "bg": (198,198,198),
            "light": (255,255,255),
            "face": (232,232,232),
            "shadow": (112,112,112),
            "dark": (0,0,0),
            "client_bg": (255,255,255),
            "title": (108,160,154),      # pastel mint
            "title_text": (240,252,252),
            "footer_text": (34,34,34),
            "mat_light": (238,238,238),
            "mat_dark": (0,0,0),
            "sparkle": (255,255,255),
        }
    return {
        "bg": (192,192,192),
        "light": (255,255,255),
        "face": (225,225,225),
        "shadow": (128,128,128),
        "dark": (0,0,0),
        "client_bg": (255,255,255),
        "title": (92,132,132),
        "title_text": (230,246,246),
        "footer_text": (26,26,26),
        "mat_light": (235,235,235),
        "mat_dark": (0,0,0),
        "sparkle": (255,255,255),
    }

# ── bitmap text (타이틀/푸터 공용) ───────────────────────────────────────
def _draw_bitmap_text(base_img, x, y, text, *, color=(0,0,0), scale=2, max_width=None):
    if not text: return (0,0)
    scale = max(1,int(scale))
    fnt = ImageFont.load_default()
    tmp = Image.new("L", (2048, 256), 0)
    d = ImageDraw.Draw(tmp)
    d.text((0,0), text, font=fnt, fill=255)
    bbox = tmp.getbbox()
    if not bbox: return (0,0)
    glyph = tmp.crop(bbox)
    if max_width is not None:
        while glyph.width*scale > max_width and scale > 1:
            scale -= 1
    scaled = glyph.resize((glyph.width*scale, glyph.height*scale), Image.NEAREST)
    mask = scaled.convert("L")
    colored = Image.new("RGBA", scaled.size, (*color,255))
    base_img.paste(colored, (x, y), mask)
    return (scaled.width, scaled.height)

# ── primitives & overlays ───────────────────────────────────────────────
def _rect1(d: ImageDraw.ImageDraw, box, color):
    d.rectangle(box, outline=color)

def _rect_thick(d: ImageDraw.ImageDraw, box, color, width):
    x0,y0,x1,y1 = box
    for k in range(width):
        d.rectangle([x0+k,y0+k,x1-k,y1-k], outline=color)

def _checker_overlay(img: Image.Image, box, alpha: int):
    """2x2 체커 패턴을 타일로 깔아 은은한 픽셀 텍스처"""
    x0,y0,x1,y1 = box
    w,h = x1-x0, y1-y0
    if w<=0 or h<=0: return
    pat = Image.new("RGBA", (2,2), (0,0,0,0))
    pd = ImageDraw.Draw(pat)
    pd.point((0,0), fill=(0,0,0,alpha))
    pd.point((1,1), fill=(0,0,0,alpha))
    tile = pat.resize((w,h), Image.NEAREST)
    img.paste(tile, (x0,y0), tile)

# ── main ────────────────────────────────────────────────────────────────
def apply_win95_frame(content, *, title=None, footer=None, theme=None):
    KAWAII = _env_bool("KAWAII", True)
    P = _pal(KAWAII)

    title  = title  or _env_str("FRAME_TITLE", "startdesk")
    footer = footer or _env_str("FOOTER_TEXT", "From My Desk")

    inset  = _env_int("FRAME_INSET", 12)
    margin = _env_int("FRAME_MARGIN", 8)
    bar_h  = _env_int("FRAME_TITLEBAR_H", 22)
    foot_h = _env_int("FOOTER_H", 38)

    BITMAP_SCALE_TITLE  = _env_int("BITMAP_SCALE_TITLE", 2)
    BITMAP_SCALE_FOOTER = _env_int("BITMAP_SCALE_FOOTER", 2)

    BEVEL_HI = _env_int("BEVEL_HIGHLIGHT", 255)
    BEVEL_LO = _env_int("BEVEL_SHADOW", 72)

    INNER_THK    = _env_int("INNER_BLACK_THK", 1)
    INNER_GAP    = _env_int("INNER_BLACK_GAP", 10)
    CONTENT_GAP  = _env_int("CONTENT_GAP", 0)

    MAT_LIGHT_THK = _env_int("MAT_LIGHT_THK", 1)   # NEW: 더블 매트 두께 조절
    MAT_DARK_THK  = _env_int("MAT_DARK_THK", 1)    # NEW

    BTN_THK      = _env_int("BTN_SYMBOL_THK", 1)
    BTN_SIZE     = _env_int("BTN_SIZE", 14)
    BTN_GAP      = _env_int("BTN_GAP", 3)

    # 질감(타이틀/푸터만 적용)
    DITHER_ON    = _env_bool("DITHER_ON", False)
    DITHER_ALPHA = _env_int("DITHER_ALPHA", 18)

    px_on  = _env_bool("PIXELATE", True)
    px_blk = _env_int("PIXELATE_BLOCK", 8)

    cW,cH = content.size
    W = cW + inset*2 + margin*2
    H = cH + inset*2 + bar_h + foot_h + margin*2

    img = Image.new("RGB", (W,H), P["bg"])
    d = ImageDraw.Draw(img)

    # — 외곽 베벨 —
    _rect1(d, (0,0,W-1,H-1), P["dark"])
    d.line([(0,0),(W-1,0)], fill=(BEVEL_HI,BEVEL_HI,BEVEL_HI))
    d.line([(0,0),(0,H-1)], fill=(BEVEL_HI,BEVEL_HI,BEVEL_HI))
    d.line([(0,H-1),(W-1,H-1)], fill=(BEVEL_LO,BEVEL_LO,BEVEL_LO))
    d.line([(W-1,0),(W-1,H-1)], fill=(BEVEL_LO,BEVEL_LO,BEVEL_LO))

    # — 타이틀바 —
    tb = (margin, margin, W-margin, margin+bar_h)
    d.rectangle(tb, fill=P["title"], outline=P["dark"])
    if DITHER_ON: _checker_overlay(img, tb, DITHER_ALPHA)

    # 아이콘
    x0 = tb[0]+6; y0 = tb[1] + (bar_h-12)//2
    d.rectangle([x0, y0, x0+18, y0+12], fill=(22,64,72), outline=P["dark"])
    for (dx,dy),col in zip([(2,2),(6,2),(2,6),(6,6)], [(234,95,68),(42,177,118),(65,135,231),(242,212,82)]):
        d.rectangle([x0+dx-1,y0+dy-1,x0+dx+3,y0+dy+3], outline=P["dark"])
        d.rectangle([x0+dx,y0+dy,x0+dx+2,y0+dy+2], fill=col)

    # 타이틀 텍스트
    left = x0 + 22
    right = tb[2] - (BTN_SIZE*3 + BTN_GAP*4) - 6
    _draw_bitmap_text(img, left, tb[1] + (bar_h - 8*BITMAP_SCALE_TITLE)//2,
                      title, color=P["title_text"], scale=BITMAP_SCALE_TITLE, max_width=right-left)

    # 버튼 (작고 통통)
    def _btn(x, y, w, h, sym: str):
        d.rectangle([x,y,x+w,y+h], fill=P["face"])
        d.line([(x,y+h),(x,y),(x+w,y)], fill=P["light"])
        d.line([(x,y+h),(x+w,y+h),(x+w,y)], fill=P["shadow"])
        _rect1(d, (x,y,x+w,y+h), P["dark"])
        cx = (x+x+w)//2; cy = (y+y+h)//2
        if sym=="minus":
            for t in range(BTN_THK): d.line([(x+4,cy+t),(x+w-4,cy+t)], fill=P["dark"])
        elif sym=="square":
            _rect_thick(d,(x+4,y+4,x+w-4,y+h-4),P["dark"], BTN_THK)
        else:
            for t in range(BTN_THK):
                d.line([(x+4,y+4+t),(x+w-4,y+h-4+t)], fill=P["dark"])
                d.line([(x+4,y+h-4-t),(x+w-4,y+4-t)], fill=P["dark"])

    bw, bh, gap = BTN_SIZE, BTN_SIZE, BTN_GAP
    xb = right + 6
    yb = tb[1] + (bar_h-bh)//2
    for i,s in enumerate(("minus","square","close")):
        _btn(xb + i*(bw+gap), yb, bw, bh, s)

    d.line([(tb[0], tb[3]), (tb[2], tb[3])], fill=P["shadow"])

    # — 클라이언트 영역 —
    client = (margin, tb[3] + margin//2, W - margin, H - foot_h - margin//2)
    _rect1(d, client, (80,80,80))
    inner = (client[0]+2, client[1]+2, client[2]-2, client[3]-2)
    d.rectangle(inner, fill=(225,225,225))

    # 검정 외곽
    border = (inner[0]+inset//2, inner[1]+inset//2, inner[2]-inset//2, inner[3]-inset//2)
    _rect_thick(d, border, P["dark"], max(1, INNER_THK))

    # 더블 매트(라이트 → 블랙) [두께 ENV로 제어]
    mat1 = (border[0]+INNER_THK, border[1]+INNER_THK, border[2]-INNER_THK, border[3]-INNER_THK)
    _rect_thick(d, mat1, P["mat_light"], max(1, MAT_LIGHT_THK))
    mat2 = (mat1[0]+MAT_LIGHT_THK, mat1[1]+MAT_LIGHT_THK, mat1[2]-MAT_LIGHT_THK, mat1[3]-MAT_LIGHT_THK)
    _rect_thick(d, mat2, P["mat_dark"], max(1, MAT_DARK_THK))

    # 넓은 화이트 매트
    white = (mat2[0]+MAT_DARK_THK, mat2[1]+MAT_DARK_THK, mat2[2]-MAT_DARK_THK, mat2[3]-MAT_DARK_THK)
    if INNER_GAP > 0:
        _rect_thick(d, white, (225,225,225), max(1, INNER_GAP))

    # 최종 캔버스
    canvas = (white[0]+INNER_GAP, white[1]+INNER_GAP, white[2]-INNER_GAP, white[3]-INNER_GAP)
    d.rectangle(canvas, fill=P["client_bg"])

    # 콘텐츠 배치
    draw_box = (canvas[0]+CONTENT_GAP, canvas[1]+CONTENT_GAP, canvas[2]-CONTENT_GAP, canvas[3]-CONTENT_GAP)
    aw,ah = draw_box[2]-draw_box[0], draw_box[3]-draw_box[1]
    r = min(aw/content.width, ah/content.height)
    nw,nh = max(1,int(content.width*r)), max(1,int(content.height*r))
    if px_on:
        b = max(1, px_blk)
        content = content.resize((max(1,nw//b), max(1,nh//b)), Image.NEAREST).resize((nw,nh), Image.NEAREST)
    else:
        content = content.resize((nw,nh))
    cx = draw_box[0] + (aw - nw)//2
    cy = draw_box[1] + (ah - nh)//2
    img.paste(content, (cx, cy))

    # — 푸터(디더 ON 시 은은한 텍스처) —
    fy0, fy1 = H - foot_h - margin, H - margin
    d.rectangle([0,fy0,W,fy1], fill=(210,205,198))
    d.line([(0,fy0),(W,fy0)], fill=P["light"])
    d.line([(0,fy1-1),(W,fy1-1)], fill=(60,60,60))
    if DITHER_ON: _checker_overlay(img, (0,fy0,W,fy1), DITHER_ALPHA)

    # 푸터 텍스트
    tw, th = _draw_bitmap_text(img, 0, 0, footer, color=P["footer_text"], scale=BITMAP_SCALE_FOOTER)
    tx = (W - tw)//2; ty = fy0 + (foot_h - th)//2
    _draw_bitmap_text(img, tx, ty, footer, color=P["footer_text"], scale=BITMAP_SCALE_FOOTER)

    return img
