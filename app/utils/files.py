# app/utils/files.py (추가)
from pathlib import Path
import random

def ensure_dirs() -> None:
    """필요한 출력 디렉터리 생성 (존재하면 무시)."""
    Path("output/images").mkdir(parents=True, exist_ok=True)
    Path("output/logs").mkdir(parents=True, exist_ok=True)

def pick_random_asset(assets_dir: Path | str):
    """assets 폴더에서 무작위 파일 하나 선택 (없으면 None)."""
    p = Path(assets_dir)
    if not p.exists():
        return None
    files = [f for f in p.glob("*") if f.is_file()]
    return random.choice(files) if files else None
