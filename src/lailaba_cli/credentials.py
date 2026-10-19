from __future__ import annotations
import os, json
from pathlib import Path
from .config import config_home, ensure_dirs

SERVICE = "lailaba-cli"

def _keyring():
    try:
        import keyring
        backend = keyring.get_keyring()
        # Avoid insecure fail backends; use file fallback when backend is unsuitable.
        if backend and "fail" not in backend.__class__.__name__.lower(): return keyring
    except Exception:
        pass
    return None

def get_api_key(provider: str | None = None) -> str | None:
    # Provider-specific environment variables prevent a Lailaba key from being
    # accidentally sent to a third-party endpoint (or vice versa).
    if provider == "lailaba":
        env = os.environ.get("LAILABA_API_KEY", "").strip()
    elif provider == "openai-compatible":
        env = (os.environ.get("LAILABA_THIRD_PARTY_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")).strip()
    else:
        env = (os.environ.get("LAILABA_API_KEY", "") or os.environ.get("LAILABA_THIRD_PARTY_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")).strip()
    if env: return env
    kr = _keyring()
    if kr:
        try:
            value = kr.get_password(SERVICE, "default")
            if value: return value
        except Exception: pass
    path = ensure_dirs() / "credentials.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("api_key") or None
    except (OSError, json.JSONDecodeError): return None

def save_api_key(key: str, *, overwrite: bool = False, provider: str | None = None) -> str:
    key = key.strip()
    if not key or "\n" in key or "\r" in key: raise ValueError("API key must be a non-empty single line.")
    existing = get_api_key(provider)
    if existing and not overwrite and existing != key: raise FileExistsError("An API key already exists; explicitly confirm replacement first.")
    kr = _keyring()
    if kr:
        try:
            kr.set_password(SERVICE, "default", key)
            return "OS credential store"
        except Exception: pass
    root = ensure_dirs(); path = root / "credentials.json"
    tmp = root / "credentials.json.tmp"
    tmp.write_text(json.dumps({"api_key": key}, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt": tmp.chmod(0o600)
    tmp.replace(path)
    if os.name != "nt": path.chmod(0o600)
    return "protected credentials.json file (OS keyring unavailable)"

def delete_api_key() -> None:
    kr = _keyring()
    if kr:
        try: kr.delete_password(SERVICE, "default")
        except Exception: pass
    path = config_home() / "credentials.json"
    try: path.unlink()
    except FileNotFoundError: pass

def mask_key(key: str | None) -> str:
    if not key: return "not configured"
    return "*" * max(4, min(12, len(key)-4)) + key[-4:]
