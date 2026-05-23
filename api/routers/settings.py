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

# Keys the frontend is allowed to set via PUT /api/settings
_ALLOWED_KEYS = {
    "session_limit", "min_score", "auto_discover", "default_mode",
    "cover_letter", "browser_visible", "company_cooldown_days", "theme",
    "accent_color", "smtp_enabled", "smtp_host", "smtp_port", "smtp_user",
    "smtp_pass", "anthropic_key", "onboarding_complete",
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
    data = _load()
    # Never expose encrypted key material — replace with boolean presence flags
    data["anthropic_key_set"] = bool(data.pop("anthropic_key_enc", ""))
    data["smtp_pass_set"]     = bool(data.pop("smtp_pass_enc", ""))
    return data


@router.put("")
def update_settings(body: Dict[str, Any]) -> Dict:
    # Strip unknown keys (no arbitrary persistence) and block direct _enc overwrite
    unknown = set(body.keys()) - _ALLOWED_KEYS
    for k in unknown:
        body.pop(k)

    current = _load()
    from api.security import encrypt
    if "anthropic_key" in body:
        val = body.pop("anthropic_key")
        if val:                                       # non-empty → encrypt and store
            current["anthropic_key_enc"] = encrypt(val)
        elif val == "":                               # explicit clear → wipe key
            current["anthropic_key_enc"] = ""
    if "smtp_pass" in body:
        val = body.pop("smtp_pass")
        if val:
            current["smtp_pass_enc"] = encrypt(val)
        elif val == "":
            current["smtp_pass_enc"] = ""

    current.update(body)
    _save(current)

    # Return safe view (no _enc fields)
    current["anthropic_key_set"] = bool(current.pop("anthropic_key_enc", ""))
    current["smtp_pass_set"]     = bool(current.pop("smtp_pass_enc", ""))
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
