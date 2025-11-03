# -*- coding: utf-8 -*-
r"""
app/publish/sync_pages.py
- GitHub Pages(또는 임의의 정적 호스팅 폴더)로 결과 파일을 동기화
- 콘솔 인코딩 이슈 방지: ASCII 로그만 사용
- 환경변수:
  PAGES_DIR      : 동기화 대상 로컬 폴더 (예: C:\\Users\\User\\newproject\\docs\\images)
  PAGES_BASE_URL : 공개 URL 베이스 (예: https://user.github.io/newproject/images)
"""

from __future__ import annotations
import os
import shutil
from pathlib import Path

def sync_to_pages(src_path: str) -> str:
    """
    src_path(로컬 생성 파일)를 PAGES_DIR로 복사.
    반환: 공개 URL(구성된 경우) 또는 대상 경로 문자열.
    """
    if not src_path:
        return ""

    src = Path(src_path)
    if not src.exists():
        return ""

    dst_root = os.getenv("PAGES_DIR", "").strip()
    base_url = os.getenv("PAGES_BASE_URL", "").strip()

    if not dst_root:
        # 대상 폴더 설정이 없으면 스킵
        try:
            print(f"[PAGES] skip (PAGES_DIR not set) src={src}")
        except Exception:
            pass
        return ""

    dst_root_p = Path(dst_root)
    dst_root_p.mkdir(parents=True, exist_ok=True)
    dst = dst_root_p / src.name

    shutil.copy2(str(src), str(dst))

    # 콘솔 인코딩 문제 방지: ASCII만 출력
    try:
        print(f"[PAGES] synced -> {dst}")
    except Exception:
        pass

    if base_url:
        return f"{base_url.rstrip('/')}/{src.name}"
    return str(dst)
