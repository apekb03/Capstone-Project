"""
Pulsoid heart-rate helpers for the game.
"""

import json
import os
import ssl
import urllib.error
import urllib.request

PULSOID_HEART_RATE_URL = "https://dev.pulsoid.net/api/v1/data/heart_rate/latest"
PULSOID_VALIDATE_URL = "https://dev.pulsoid.net/api/v1/token/validate"


def _load_dotenv() -> None:
    """Load .env values into process environment (no dependency)."""
    for path in (os.path.join(os.path.dirname(__file__), ".env"), ".env"):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as file_obj:
                for raw_line in file_obj:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key:
                        os.environ.setdefault(key, value)
        except OSError:
            pass
        break


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return ctx


def validate_token(access_token: str):
    """Return (True, payload) if valid token with heart-rate scope."""
    req = urllib.request.Request(
        PULSOID_VALIDATE_URL,
        method="GET",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        if err.code == 401:
            return False, "Token invalid or expired."
        return False, f"Validation failed ({err.code})."
    except (urllib.error.URLError, json.JSONDecodeError) as err:
        return False, f"Validation error: {err}"

    scopes = data.get("scopes") or []
    if "data:heart_rate:read" not in scopes:
        return False, "Token missing data:heart_rate:read scope."
    return True, data


def get_heart_rate(access_token: str):
    """Fetch latest Pulsoid heart rate; returns int or None."""
    req = urllib.request.Request(
        PULSOID_HEART_RATE_URL + "?response_mode=text_plain_only_heart_rate",
        method="GET",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context()) as resp:
            text = resp.read().decode().strip()
            return int(text) if text.isdigit() else None
    except urllib.error.HTTPError as err:
        if err.code == 412:
            return None
        return None
    except (urllib.error.URLError, ValueError):
        return None


_load_dotenv()
