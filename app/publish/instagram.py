# -*- coding: utf-8 -*-
"""
app/publish/instagram.py
- DRY/LIVE 안전가드 포함 업로드 모듈
- DRY_RUN 이거나 토큰/유저ID/이미지URL이 없으면 업로드를 '시뮬레이션'하고 종료
- LIVE 업로드는 Instagram Graph API (media -> media_publish) 표준 흐름
  * 사전조건: 이미지가 '공개 URL'로 접근 가능해야 함 (image_url)
  * 권장: sync_to_pages()로 PAGES_BASE_URL 하에 업로드 파일이 노출되도록 구성
환경변수:
  INSTAGRAM_TOKEN     = EAA... (User Access Token 또는 Long-Lived)
  INSTAGRAM_USER_ID   = 1784... (instagram_business_account.id)
"""

from __future__ import annotations
import os
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests

log = logging.getLogger("instagram")

GRAPH_VER = os.getenv("FB_GRAPH_VER", "v21.0").strip()  # 필요 시 조정

def _env_bool(v: Optional[str], default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1","true","yes","y","on")

def _get_envs() -> Dict[str, str]:
    return {
        "token": os.getenv("INSTAGRAM_TOKEN", "").strip(),
        "user_id": os.getenv("INSTAGRAM_USER_ID", "").strip(),
        # image_url은 코드에서 계산/주입
    }

def _build_image_url(local_path: str) -> str:
    """
    로컬 파일 경로를 공개 URL로 변환.
    - sync_to_pages()가 반환한 URL을 main.py에서 넘기는 게 가장 깔끔하지만,
      혹시 비어 있으면 PAGES_BASE_URL + 파일명 으로 시도한다.
    """
    base = os.getenv("PAGES_BASE_URL", "").strip()
    if not base:
        return ""
    name = Path(local_path).name
    return f"{base.rstrip('/')}/{name}"

def _post_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(url, data=params, timeout=30)
    try:
        return r.json()
    except Exception:
        return {"status_code": r.status_code, "text": r.text}

def publish_image(
    *,
    local_path: str,
    caption: str,
    hashtags: List[str] | None = None,
    dry_run: bool = True,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Params
    ------
    local_path : 로컬 생성 파일 경로 (기록/표시용)
    caption    : 본문(해시태그 포함 권장)
    hashtags   : (옵션) 별도 해시태그 배열. 기본은 빈 리스트 (중복 방지)
    dry_run    : True이면 시뮬레이션만 수행
    image_url  : 공개 접근 가능한 이미지 URL (없으면 PAGES_BASE_URL + 파일명으로 시도)

    Returns
    -------
    dict : { mode, user_id, image_url, container_id, publish_id, error, ... }
    """
    envs = _get_envs()
    token = envs["token"]
    user_id = envs["user_id"]
    mode = "DRY" if dry_run else "LIVE"

    # 이미지 URL 확보
    img_url = image_url or _build_image_url(local_path)

    # 공통 요약 (로그/리턴용)
    summary = {
        "mode": mode,
        "user_id": f"{user_id[:4]}xxxxxxxxxxxxx" if user_id else "",
        "image_url": img_url,
        "caption": caption,
        "local_path": local_path,
    }

    # DRY거나 필수값 없음 → 시뮬레이션 종료
    if dry_run or not token or not user_id or not img_url:
        try:
            print("✓ DRY RUN - 업로드 시뮬레이션")
            print(f" - user_id: {summary['user_id']}")
            print(f" - image_url: {img_url or '(missing)'}")
            print(f" - caption: {caption.splitlines()[0][:120]}...")
        except Exception:
            pass
        summary["note"] = "skipped (dry_run or missing token/user_id/image_url)"
        return summary

    # LIVE 업로드 시작
    try:
        # 1) container 생성
        create_url = f"https://graph.facebook.com/{GRAPH_VER}/{user_id}/media"
        params = {
            "image_url": img_url,
            "caption": caption,
            "access_token": token,
        }
        c = _post_json(create_url, params)
        if "id" not in c:
            return {**summary, "error": "container_create_failed", "response": c}

        container_id = c["id"]
        # 2) 게시
        publish_url = f"https://graph.facebook.com/{GRAPH_VER}/{user_id}/media_publish"
        p = _post_json(publish_url, {"creation_id": container_id, "access_token": token})
        if "id" not in p:
            return {**summary, "container_id": container_id, "error": "publish_failed", "response": p}

        publish_id = p["id"]

        # 3) 완료 확인(간단 폴링 선택)
        status_url = f"https://graph.facebook.com/{GRAPH_VER}/{publish_id}?fields=id,status_code&access_token={token}"
        time.sleep(1.0)
        status = requests.get(status_url, timeout=15).json()

        return {
            **summary,
            "container_id": container_id,
            "publish_id": publish_id,
            "status": status,
        }
    except Exception as e:
        return {**summary, "error": str(e)}
