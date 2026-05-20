"""Application settings persistence."""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR     = Path(__file__).parent.parent.parent
SETTINGS_FILE = BASE_DIR / "config" / "settings.json"
BLACKLIST_FILE = BASE_DIR / "config" / "blacklist.json"

router = APIRouter()

_DEFAULTS: Dict[str, Any] = {
    "session_limit": 25,
    "min_score": 0.05,
    "auto_discover": False,
    "default_mode": "auto",
    "cover_letter": True,
    "browser_visible": True,
    "company_cooldown_days": 30,
    "theme": "dark",
    "accent_color": "indigo",
    "smtp_enabled": False,
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_pass_enc": "",
    "anthropic_key_enc": "",
    "onboarding_complete": False,
}


def _load() -> Dict:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
            return {**_DEFAULTS, **data}
        except Exception:
            pass
    return dict(_DEFAULTS)


def _save(data: Dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.get("")
def get_settings() -> Dict:
    return _load()


@router.put("")
def update_settings(body: Dict[str, Any]) -> Dict:
    current = _load()
    # Encrypt sensitive fields before storing
    from api.security import encrypt
    if "anthropic_key" in body and body["anthropic_key"]:
        body["anthropic_key_enc"] = encrypt(body.pop("anthropic_key"))
    if "smtp_pass" in body and body["smtp_pass"]:
        body["smtp_pass_enc"] = encrypt(body.pop("smtp_pass"))
    current.update(body)
    _save(current)
    return current


@router.post("/test-browser")
def test_browser():
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "chromium", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return {"success": True, "message": "Browser ready"}
        # Try install
        install = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=120,
        )
        if install.returncode == 0:
            return {"success": True, "message": "Browser installed successfully"}
        return {"success": False, "message": install.stderr[:200]}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/blacklist")
def get_blacklist() -> List[str]:
    if BLACKLIST_FILE.exists():
        try:
            with open(BLACKLIST_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


@router.put("/blacklist")
def update_blacklist(body: List[str]) -> List[str]:
    BLACKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(body, f, indent=2)
    return body


@router.get("/token")
def get_token():
    """Public endpoint — returns the server session token for the UI."""
    from api.security import API_TOKEN
    return {"token": API_TOKEN}
