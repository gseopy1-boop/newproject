# app/utils/profiles.py
# -*- coding: utf-8 -*-
import os
import json
from typing import Dict, Any, Optional

class ProfileNotFound(Exception):
    pass

def _repo_root() -> str:
    # 현재 파일 기준으로 프로젝트 루트 추정: app/utils/ -> 루트
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))

def _profiles_path() -> str:
    return os.path.join(_repo_root(), "profiles.json")

def _load_profiles() -> Dict[str, Any]:
    path = _profiles_path()
    if not os.path.exists(path):
        # profiles.json 자체가 없다면 빈 dict
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f) or {}

def _resolve_pid(pid: Optional[str], existing_keys: set) -> str:
    # 1) 인자 우선, 없으면 환경변수 PROFILE, 그것도 없으면 'kr'
    resolved = (pid or os.getenv("PROFILE") or "kr").strip().lower()

    # 2) 별칭 매핑 (profiles.json에 main이 없어도 kr로 연결)
    aliases = {
        "main": "kr",
    }
    # 이미 존재하면 그대로 사용
    if resolved in existing_keys:
        return resolved
    # 존재하지 않으면 별칭 적용
    mapped = aliases.get(resolved, resolved)
    if mapped in existing_keys:
        return mapped
    return mapped  # 마지막 검증은 get_profile에서 함

def get_profile(pid: Optional[str] = None) -> Dict[str, Any]:
    profiles = _load_profiles()
    keys = set(k.lower() for k in profiles.keys())
    resolved = _resolve_pid(pid, keys)

    # 다시 한 번 존재 확인
    if resolved not in keys:
        # 대소문자 구분 없이 찾기
        for k in profiles.keys():
            if k.lower() == resolved:
                resolved = k
                break
        else:
            raise ProfileNotFound(f"profile '{pid or os.getenv('PROFILE') or 'kr'}' not found. "
                                  f"Check profiles.json or set PROFILE env.")

    # 원래 키 보존
    real_key = None
    for k in profiles.keys():
        if k.lower() == resolved:
            real_key = k
            break

    prof = profiles[real_key] if real_key else {}
    # id 필드 보강(없으면 키 이름)
    if isinstance(prof, dict) and "id" not in prof:
        prof["id"] = real_key or resolved
    return prof
