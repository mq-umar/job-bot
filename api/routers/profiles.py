"""Profile CRUD endpoints."""
import json
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR   = Path(__file__).parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"

router = APIRouter()


def _profile_path(name: str) -> Path:
    return CONFIG_DIR / f"{name}_profile.json"


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
