import os
from pathlib import Path

from dotenv import load_dotenv

try:
    import keyring
except ImportError:
    keyring = None


# Load local environment variables regardless of the current working directory.
load_dotenv(Path(__file__).resolve().parent / ".env")

KEYRING_SERVICE = "Music Tag Editor"
KEYRING_ACCOUNT = "GEMINI_API_KEY"


def get_gemini_api_key():
    """Return the key from the environment first, then the OS credential store."""
    environment_key = os.getenv("GEMINI_API_KEY", "").strip()
    if environment_key:
        return environment_key
    if keyring is None:
        return ""
    try:
        return (keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT) or "").strip()
    except Exception:
        return ""


def get_gemini_key_source():
    if os.getenv("GEMINI_API_KEY", "").strip():
        return "environment"
    if get_gemini_api_key():
        return "keyring"
    return "missing"


def save_gemini_api_key(api_key):
    if keyring is None:
        raise RuntimeError("The keyring package is not installed.")
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("API key cannot be empty.")
    keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, api_key)


def delete_gemini_api_key():
    if keyring is None:
        raise RuntimeError("The keyring package is not installed.")
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
    except keyring.errors.PasswordDeleteError:
        pass


# Kept for compatibility with older imports. New code should call the getter so
# credentials changed in the running application take effect immediately.
GEMINI_API_KEY = get_gemini_api_key()
