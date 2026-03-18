"""
Firebase Auth helpers for Python.

This module supports:
- Email/password sign-in via Firebase Identity Toolkit REST API (client-side style)
- ID token verification via firebase-admin (server-side)
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


def _ssl_context() -> ssl.SSLContext:
    """SSL context that works on macOS (uses certifi bundle if available)."""
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return ctx


def _load_dotenv() -> None:
    # Keep same lightweight pattern as pulsoid_heartrate.py
    for path in (os.path.join(os.path.dirname(__file__), ".env"), ".env"):
        if not os.path.isfile(path):
            continue
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key:
                            os.environ.setdefault(key, value)
        except OSError:
            pass
        break


_load_dotenv()


class FirebaseAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class FirebaseSignInResult:
    id_token: str
    refresh_token: str | None
    expires_in: int | None
    local_id: str | None
    email: str | None
    raw: dict[str, Any]


def sign_up_with_email_password(*, api_key: str, email: str, password: str) -> FirebaseSignInResult:
    """
    Create a new Firebase Auth user (email/password) via REST API.

    If successful, Firebase returns an ID token (i.e., the user is effectively signed in).
    """
    url = "https://identitytoolkit.googleapis.com/v1/accounts:signUp" f"?key={api_key}"
    payload = json.dumps(
        {"email": email, "password": password, "returnSecureToken": True}
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        if e.fp:
            try:
                body = e.fp.read().decode("utf-8")
            except Exception:
                body = ""
        try:
            err = json.loads(body).get("error", {})
            msg = err.get("message") or body or e.reason
        except Exception:
            msg = body or e.reason
        raise FirebaseAuthError(f"Firebase sign-up failed ({e.code}): {msg}") from e
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        raise FirebaseAuthError(f"Firebase sign-up failed: {e}") from e

    id_token = data.get("idToken")
    if not id_token:
        raise FirebaseAuthError(f"Firebase sign-up response missing idToken: {data}")

    expires_in = None
    try:
        expires_in = int(data["expiresIn"]) if "expiresIn" in data else None
    except Exception:
        expires_in = None

    return FirebaseSignInResult(
        id_token=id_token,
        refresh_token=data.get("refreshToken"),
        expires_in=expires_in,
        local_id=data.get("localId"),
        email=data.get("email"),
        raw=data,
    )


def sign_in_with_email_password(*, api_key: str, email: str, password: str) -> FirebaseSignInResult:
    """
    Sign-in using Firebase Auth email/password (Identity Toolkit REST API).

    Returns an ID token you can send to your backend for verification.
    """
    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={api_key}"
    )
    payload = json.dumps(
        {"email": email, "password": password, "returnSecureToken": True}
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        if e.fp:
            try:
                body = e.fp.read().decode("utf-8")
            except Exception:
                body = ""
        try:
            err = json.loads(body).get("error", {})
            msg = err.get("message") or body or e.reason
        except Exception:
            msg = body or e.reason
        raise FirebaseAuthError(f"Firebase sign-in failed ({e.code}): {msg}") from e
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        raise FirebaseAuthError(f"Firebase sign-in failed: {e}") from e

    id_token = data.get("idToken")
    if not id_token:
        raise FirebaseAuthError(f"Firebase sign-in response missing idToken: {data}")

    expires_in = None
    try:
        expires_in = int(data["expiresIn"]) if "expiresIn" in data else None
    except Exception:
        expires_in = None

    return FirebaseSignInResult(
        id_token=id_token,
        refresh_token=data.get("refreshToken"),
        expires_in=expires_in,
        local_id=data.get("localId"),
        email=data.get("email"),
        raw=data,
    )


def verify_id_token(*, id_token: str, service_account_json_path: str) -> dict[str, Any]:
    """
    Verify a Firebase ID token using firebase-admin (server-side verification).

    You should run this in your backend, not on untrusted clients.
    """
    try:
        import firebase_admin
        from firebase_admin import auth, credentials
    except Exception as e:
        raise FirebaseAuthError(
            "Missing dependency: firebase-admin. Install it and try again."
        ) from e

    if not os.path.isfile(service_account_json_path):
        raise FirebaseAuthError(
            f"Service account JSON not found: {service_account_json_path}"
        )

    # Initialize only once per process
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_json_path)
        firebase_admin.initialize_app(cred)

    try:
        decoded = auth.verify_id_token(id_token)
    except Exception as e:
        raise FirebaseAuthError(f"ID token verification failed: {e}") from e

    # decoded includes: uid, email (if present), iss, aud, exp, iat, etc.
    return dict(decoded)


def env_or_raise(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise FirebaseAuthError(f"Missing environment variable: {name}")
    return val

