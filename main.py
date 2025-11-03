from __future__ import annotations
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv; load_dotenv()
import os, json, logging, inspect, shutil, io
from typing import List, Optional

# ─────────────────────────────────────────────────────────────
# NEW: 우리 자동화 모듈 사용 (429 폴백 포함)
from automation.trends import TrendClient
trend_client = TrendClient()
from automation.prompt_builder import build_image_prompt
from automation.caption_builder import build_caption

# 기존 유틸/퍼블리셔는 그대로 사용
from app.publish.sync_pages import sync_to_pages
from app.publish.instagram import publish_image
from app.utils.files import pick_random_asset, ensure_dirs
from app.utils.profiles import get_profile
from app.utils.themes import pick_theme, theme_to_prompt_hint  # 있으면 사용, 없으면 theme_hint=None
from app.nlp.dw_frame import (
    DigitalWorkspaceFrame, CRTMonitor, Keyboard, Mouse, DocumentFile,
    to_prompt as dw_to_prompt, apply_signage_env as dw_apply_signage_env,
)
# 프로젝트의 실제 이미지 생성 함수 (원본 그대로)
from app.media.image_gen import generate_image_with_reference

# PIL (리사이즈/재압축)
try:
    from PIL import Image
except Exception:
    Image = None

# ─────────────────────────────────────────────────────────────
# 로거 & JSON 로그 저장
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")

def save_run_log(ts: str, payload: dict):
    p = Path("output/logs") / f"post_{ts}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────────────────────
# 이미지 생성기 호환 래퍼 (시그니처 자동 감지 + 저장/리사이즈)
def _save_image_like(obj, out_path: str, target_side: int, to_jpeg: bool, max_size_mb: float):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(obj, (str, os.PathLike)):
        src = Path(obj)
        if src.exists():
            if Image is None:
                shutil.copyfile(src, out)
                return str(out)
            with Image.open(src) as im:
                return _save_pil(im, out, target_side, to_jpeg, max_size_mb)

    if isinstance(obj, dict):
        for k in ("path", "out_path", "output", "file", "save_path"):
            v = obj.get(k)
            if v:
                return _save_image_like(v, out, target_side, to_jpeg, max_size_mb)
        for k in ("bytes", "data", "content"):
            v = obj.get(k)
            if isinstance(v, (bytes, bytearray)):
                return _save_bytes(v, out, to_jpeg)

    if isinstance(obj, (bytes, bytearray)):
        return _save_bytes(obj, out, to_jpeg)

    if Image is not None and getattr(obj, "save", None):
        try:
            return _save_pil(obj, out, target_side, to_jpeg, max_size_mb)
        except Exception:
            pass

    if Image is not None:
        im = Image.new("RGB", (1080, 1080), (230, 230, 230))
        return _save_pil(im, out, target_side, to_jpeg, max_size_mb)

    out.write_bytes(b"")
    return str(out)

def _save_bytes(b: bytes, out: Path, to_jpeg: bool) -> str:
    if to_jpeg and Image is not None:
        try:
            im = Image.open(io.BytesIO(b)).convert("RGB")
            im.save(out, format="JPEG", quality=90, optimize=True)
            return str(out)
        except Exception:
            pass
    out.write_bytes(b)
    return str(out)

def _save_pil(im, out: Path, target_side: int, to_jpeg: bool, max_size_mb: float) -> str:
    if Image is None:
        out.write_bytes(b"")
        return str(out)

    im = im.convert("RGBA")
    w, h = im.size
    max_side = max(w, h)
    if target_side and max_side > target_side:
        scale = target_side / max_side
        im = im.resize((int(w * scale), int(h * scale)), resample=Image.LANCZOS)

    if to_jpeg:
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
        fmt = "JPEG"
    else:
        fmt = "PNG"

    q = 92
    for _ in range(6):
        params = {"format": fmt}
        if fmt == "JPEG":
            params.update({"quality": q, "optimize": True})
        im.save(out, **params)
        if out.stat().st_size <= int(max_size_mb * 1024 * 1024):
            break
        q = max(70, q - 5)
    return str(out)

def generate_with_ref_compat(*, prompt: str, reference_path: Optional[str], out_path: str,
                             target_side: int = 1080, to_jpeg: bool = True, max_size_mb: float = 2.0):
    sig = inspect.signature(generate_image_with_reference)
    params = sig.parameters
    call_kwargs = {}
    if "prompt" in params:
        call_kwargs["prompt"] = prompt
    for name in ("reference_img_path", "reference_path", "ref_path", "reference"):
        if name in params:
            call_kwargs[name] = reference_path
            break
    result = generate_image_with_reference(**call_kwargs)
    return _save_image_like(result, out_path, target_side, to_jpeg, max_size_mb)

# ─────────────────────────────────────────────────────────────
def run_post_cycle():
    ROOT = Path(__file__).resolve().parent
    load_dotenv(dotenv_path=ROOT / ".env")
    ensure_dirs()  # output/images, output/logs

    # 1) 트렌드 키워드 (429 자동 처리 + 폴백)
    kws: List[str] = []
    try:
        kws = trend_client.get_daily_keywords(limit=30) or []
        source_note = "trends"
    except Exception as e:
        log.warning(f"[trends] fetch error: {e}")
        source_note = "error"

    if isinstance(kws, str):
        kws = [kws]
    if not kws:
        kws = ["fashion", "travel", "iphone"]
        source_note = "fallback"

    # 키워드 3개 선정
    k3 = [x for x in kws if isinstance(x, str) and x.strip()][:3]
    while len(k3) < 3:
        k3.append("memory")

    # 2) 참고 이미지(있어도 되고 없어도 됨)
    ref = pick_random_asset(ROOT / "assets")
    ref_path = str(ref) if ref else None

    # 3) 프로필/로케일 (PROFILE=main → profiles.json의 kr로 매핑됨)
    try:
        profile = get_profile(None)
    except Exception:
        profile = {"id": "main", "locale": "ko"}
    locale = profile.get("locale", "ko")

    # 4) 테마/프롬프트/캡션
    try:
        theme = pick_theme(None)  # 프로젝트 util 있으면 사용
        theme_hint = theme_to_prompt_hint(theme)
    except Exception:
        theme, theme_hint = {}, None

    # === (옵션) Digital Workspace 청사진 모드 ===
    use_dw = os.getenv("USE_DW_BLUEPRINT", "1").lower() in ("1", "true", "yes", "on")
    dw_prompt_hint = None
    if use_dw:
        dw = DigitalWorkspaceFrame(
            title=os.getenv("DW_TITLE", "Exploring the Digital Workspace"),
            series=os.getenv("DW_SERIES", "From My Desk"),
        ).add(CRTMonitor()).add(Keyboard()).add(Mouse()).add(DocumentFile())
        # 로고/풋터/헤드라인/env 세팅 (+픽셀화 On)
        dw_apply_signage_env(dw, pixelate=True)
        # 프롬프트 힌트 문자열
        dw_prompt_hint = dw_to_prompt(dw)

    # 기본 프롬프트/캡션 생성
    prompt_dict = build_image_prompt(k3, theme_hint=theme_hint, seed=None, locale=locale)
    caption = build_caption(k3, theme_hint=prompt_dict.get("theme_key"), seed=None)

    # 최종 이미지용 프롬프트: 기본 프롬프트 + (옵션) 테마 힌트 + (옵션) DW 청사진
    prompt_chunks = [
        prompt_dict.get("prompt"),
        theme_hint,
        dw_prompt_hint,
    ]
    prompt_for_image = " | ".join([p for p in prompt_chunks if p]).strip(" |")

    
    # 5) 출력 경로
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"post_{ts}.jpg"
    out_path = str(ROOT / "output" / "images" / filename)

    # 6) 이미지 생성 → 저장
    img_path = generate_with_ref_compat(
        prompt=prompt_for_image,
        reference_path=ref_path,
        out_path=out_path,
        target_side=1080,
        to_jpeg=True,
        max_size_mb=2.0,
    )

    # 7) GitHub Pages 동기화
    public_url = sync_to_pages(out_path)

    # 8) 업로드 (DRY RUN 기본)
    dry_run_env = os.getenv("DRY_RUN", "1").lower() in ("1", "true", "yes")
    publish_result = publish_image(
        local_path=out_path,
        caption=caption,
        hashtags=[],      # caption에 해시태그 포함됨 (중복 방지)
        dry_run=dry_run_env,
    )

    # 9) 로그 저장
    runlog = {
        "timestamp": ts,
        "keywords": kws,
        "k3": k3,
        "caption": caption,
        "image_path": img_path,
        "public_url": public_url,
        "publish_result": publish_result,
        "source_note": source_note,
        "dry_run": dry_run_env,
        "theme_hint": prompt_dict["theme_key"],
        "prompt": prompt_for_image,
        "negative": prompt_dict.get("negative"),
        "locale": locale,
        "profile": {k: profile.get(k) for k in ("id", "handle", "locale")},
        "reference_asset": ref_path,
    }
    save_run_log(ts, runlog)

    # 콘솔 요약
    log.info("✅ 1회 사이클 완료 (DRY RUN)" if dry_run_env else "✅ 1회 사이클 완료 (LIVE)")
    log.info(f" - 키워드: {', '.join(k3)}")
    log.info(f" - 참고 이미지: {Path(ref_path).name if ref_path else 'N/A'}")
    log.info(f" - 결과 파일: {out_path}")
    log.info(f" - GitHub Pages URL: {public_url}")
    log.info(f" - 캡션(요약): {caption[:120]}...")

if __name__ == "__main__":
    run_post_cycle()
