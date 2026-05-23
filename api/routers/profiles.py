"""Profile CRUD endpoints."""
import json
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR   = Path(__file__).parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
_CONFIG_RESOLVED = CONFIG_DIR.resolve()

router = APIRouter()


def _safe_profile_name(name: str) -> str:
    """Reject traversal sequences, path separators, and suspicious characters."""
    if not name or ".." in name or "/" in name or "\\" in name or "\x00" in name:
        raise HTTPException(status_code=400, detail="Invalid profile name")
    # Allow only alphanumeric, hyphen, underscore
    import re as _re
    if not _re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise HTTPException(status_code=400, detail="Profile name may only contain letters, numbers, hyphens, and underscores")
    return name


def _profile_path(name: str) -> Path:
    _safe_profile_name(name)
    path = CONFIG_DIR / f"{name}_profile.json"
    # Verify resolved path stays within config dir
    try:
        path.resolve().relative_to(_CONFIG_RESOLVED)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile name")
    return path


def _load_profile(name: str) -> Dict:
    p = _profile_path(name)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    with open(p) as f:
        return json.load(f)


@router.get("")
def list_profiles() -> List[Dict]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    profiles = []
    for path in CONFIG_DIR.glob("*_profile.json"):
        try:
            with open(path) as f:
                data = json.load(f)
            name = path.stem.replace("_profile", "")
            profiles.append({"name": name, **data})
        except Exception:
            pass
    return profiles


@router.get("/{name}")
def get_profile(name: str) -> Dict:
    return _load_profile(name)


@router.put("/{name}")
def update_profile(name: str, body: Dict[str, Any]) -> Dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = _profile_path(name)
    existing = {}
    if path.exists():
        with open(path) as f:
            existing = json.load(f)
    existing.update(body)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)
    return existing


@router.post("")
def create_profile(body: Dict[str, Any]) -> Dict:
    name = body.get("name") or body.get("first_name", "").lower()
    if not name:
        raise HTTPException(status_code=400, detail="Profile must have a 'name' field")
    path = _profile_path(name)
    if path.exists():
        raise HTTPException(status_code=409, detail=f"Profile '{name}' already exists")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(body, f, indent=2)
    return {"name": name, **body}


@router.delete("/{name}")
def delete_profile(name: str):
    path = _profile_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    path.unlink()
    return {"deleted": name}
