from __future__ import annotations

import os
import time
from typing import Any

from firebase_auth import FirebaseAuthError


def _init_admin() -> None:
    """
    Initialize firebase-admin for Realtime Database access.

    Required env vars:
    - FIREBASE_SERVICE_ACCOUNT_JSON: absolute path to service account JSON
    - FIREBASE_DATABASE_URL: e.g. https://capstone-project-71eda-default-rtdb.firebaseio.com/:leaderboard
    """
    try:
        import firebase_admin
        from firebase_admin import credentials
    except Exception as e:
        raise FirebaseAuthError("Missing dependency: firebase-admin.") from e

    if firebase_admin._apps:
        return

    sa_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    db_url = os.environ.get("FIREBASE_DATABASE_URL")
    if not sa_path:
        raise FirebaseAuthError("Missing environment variable: FIREBASE_SERVICE_ACCOUNT_JSON")
    if not db_url:
        raise FirebaseAuthError("Missing environment variable: FIREBASE_DATABASE_URL")
    if not os.path.isfile(sa_path):
        raise FirebaseAuthError(f"Service account JSON not found: {sa_path}")

    cred = credentials.Certificate(sa_path)
    firebase_admin.initialize_app(cred, {"databaseURL": db_url})


def submit_score(*, uid: str, email: str | None, score: int) -> dict[str, Any]:
    """
    Save a user's best score to Realtime Database under:
      /leaderboard/users/{uid}

    We keep `bestScore` as the max score and update timestamps.
    """
    _init_admin()
    from firebase_admin import db  # type: ignore

    user_ref = db.reference(f"leaderboard/users/{uid}")
    now_ms = int(time.time() * 1000)

    def _tx(current: Any) -> dict[str, Any]:
        if not isinstance(current, dict):
            current = {}
        best = current.get("bestScore")
        try:
            best_int = int(best) if best is not None else None
        except Exception:
            best_int = None

        new_best = score if best_int is None else max(best_int, score)
        out = dict(current)
        out["uid"] = uid
        if email:
            out["email"] = email
        out["bestScore"] = int(new_best)
        out.setdefault("createdAtMs", now_ms)
        out["updatedAtMs"] = now_ms
        return out

    # Transaction prevents overwriting races
    return user_ref.transaction(_tx)


def get_top_scores(*, limit: int = 10) -> list[dict[str, Any]]:
    """
    Read top scores from:
      /leaderboard/users

    NOTE: RTDB can order by ONE child; we order by bestScore and take last N,
    then reverse so highest is first.
    """
    _init_admin()
    from firebase_admin import db  # type: ignore

    query = (
        db.reference("leaderboard/users")
        .order_by_child("bestScore")
        .limit_to_last(int(limit))
    )
    data = query.get() or {}
    if not isinstance(data, dict):
        return []

    rows = list(data.values())
    rows.sort(key=lambda r: int(r.get("bestScore", 0)), reverse=True)
    return rows[: int(limit)]

