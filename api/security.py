"""
Security: session token (CSRF-like protection) + Fernet encryption for sensitive fields.
Falls back to a local key file if keyring is unavailable.
"""
from secrets import token_hex
from pathlib import Path
from typing import Optional

try:
    from cryptography.fernet import Fernet
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

try:
    import keyring
    _KEYRING_OK = True
except ImportError:
    _KEYRING_OK = False

BASE_DIR = Path(__file__).parent.parent
_KEY_FILE = BASE_DIR / ".bot_key"

# Generated once per server process. All UI requests must include this.
API_TOKEN: str = token_hex(32)


def get_or_create_key() -> bytes:
    """Return the Fernet encryption key, creating it on first run."""
    if _KEYRING_OK:
        try:
            stored = keyring.get_password("job-bot", "encryption-key")
            if stored:
                return stored.encode()
            key = Fernet.generate_key().decode()
            keyring.set_password("job-bot", "encryption-key", key)
            return key.encode()
        except Exception:
            pass
    # File-based fallback
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    return key


def encrypt(value: str) -> str:
    if not _CRYPTO_OK or not value:
        return value
    try:
        f = Fernet(get_or_create_key())
        return f.encrypt(value.encode()).decode()
    except Exception:
        return value


def decrypt(value: str) -> str:
    if not _CRYPTO_OK or not value:
        return value
    try:
        f = Fernet(get_or_create_key())
        return f.decrypt(value.encode()).decode()
    except Exception:
        return value


def verify_token(token: Optional[str]) -> bool:
    """Return True if the provided token matches the server's API_TOKEN."""
    if not token:
        return False
    return token == API_TOKEN
