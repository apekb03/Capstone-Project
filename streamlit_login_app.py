from __future__ import annotations

import time

import streamlit as st

from firebase_auth import (
    FirebaseAuthError,
    env_or_raise,
    sign_in_with_email_password,
    sign_up_with_email_password,
)
from firebase_rtdb import get_top_scores, submit_score


st.set_page_config(page_title="Firebase Login (Python)", page_icon="🔐", layout="centered")


def _is_logged_in() -> bool:
    return bool(st.session_state.get("firebase_id_token"))


def _logout() -> None:
    for k in ("firebase_id_token", "firebase_email", "firebase_local_id"):
        st.session_state.pop(k, None)


st.title("Firebase Login (Python)")
st.caption("Email/password sign-in using Firebase Auth, from a Python UI.")

with st.sidebar:
    st.subheader("Config")
    st.write("Set `FIREBASE_API_KEY` in `Capstone-Project/.env`.")
    try:
        api_key = env_or_raise("FIREBASE_API_KEY")
        st.success("FIREBASE_API_KEY is set")
    except FirebaseAuthError:
        api_key = ""
        st.error("Missing FIREBASE_API_KEY")

    if _is_logged_in():
        st.divider()
        st.subheader("Session")
        st.write(f"Email: `{st.session_state.get('firebase_email','')}`")
        st.write(f"Local ID: `{st.session_state.get('firebase_local_id','')}`")
        if st.button("Log out"):
            _logout()
            st.rerun()


if _is_logged_in():
    st.success("You are logged in.")
    st.write("Your Firebase ID token is stored in `st.session_state.firebase_id_token`.")
    with st.expander("Show ID token"):
        st.code(st.session_state["firebase_id_token"])

    st.divider()
    st.subheader("Leaderboard")

    col1, col2 = st.columns([1, 1])
    with col1:
        score = st.number_input("Your score", min_value=0, step=1, value=0)
        if st.button("Submit score"):
            uid = st.session_state.get("firebase_local_id") or ""
            email = st.session_state.get("firebase_email") or None
            if not uid:
                st.error("Missing user id in session. Please log out and log in again.")
            else:
                try:
                    saved = submit_score(uid=uid, email=email, score=int(score))
                except Exception as e:
                    st.error(
                        "Could not save to Realtime Database. "
                        "Set FIREBASE_SERVICE_ACCOUNT_JSON and FIREBASE_DATABASE_URL in `.env`.\n\n"
                        f"Details: {e}"
                    )
                else:
                    st.success(f"Saved. Your best score is {saved.get('bestScore')}.")

    with col2:
        top_n = st.number_input("Show top N", min_value=1, max_value=100, value=10, step=1)
        st.button("Refresh leaderboard")

    try:
        rows = get_top_scores(limit=int(top_n))
    except Exception as e:
        st.info(
            "Leaderboard not connected yet. "
            "Set FIREBASE_SERVICE_ACCOUNT_JSON and FIREBASE_DATABASE_URL in `.env`.\n\n"
            f"Details: {e}"
        )
        rows = []

    if rows:
        st.dataframe(
            [
                {
                    "rank": i + 1,
                    "bestScore": r.get("bestScore", 0),
                    "email": r.get("email", ""),
                    "uid": r.get("uid", ""),
                    "updatedAtMs": r.get("updatedAtMs", ""),
                }
                for i, r in enumerate(rows)
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No scores yet.")
else:
    tab_sign_in, tab_sign_up = st.tabs(["Sign in", "Sign up"])

    with tab_sign_in:
        with st.form("login"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign in")

        if submit:
            if not api_key:
                st.error("Missing FIREBASE_API_KEY. Set it in `Capstone-Project/.env`.")
            elif not email or not password:
                st.error("Enter both email and password.")
            else:
                try:
                    result = sign_in_with_email_password(
                        api_key=api_key,
                        email=email,
                        password=password,
                    )
                except FirebaseAuthError as e:
                    st.error(str(e))
                else:
                    st.session_state["firebase_id_token"] = result.id_token
                    st.session_state["firebase_email"] = result.email or email
                    st.session_state["firebase_local_id"] = result.local_id or ""
                    st.rerun()

    with tab_sign_up:
        with st.form("signup"):
            new_email = st.text_input("Email", placeholder="you@example.com", key="su_email")
            new_password = st.text_input("Password", type="password", key="su_password")
            confirm_password = st.text_input(
                "Confirm password", type="password", key="su_confirm_password"
            )
            submit_signup = st.form_submit_button("Create account")

        if submit_signup:
            if not api_key:
                st.error("Missing FIREBASE_API_KEY. Set it in `Capstone-Project/.env`.")
            elif not new_email or not new_password:
                st.error("Enter both email and password.")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters (Firebase requirement).")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                try:
                    result = sign_up_with_email_password(
                        api_key=api_key,
                        email=new_email,
                        password=new_password,
                    )
                except FirebaseAuthError as e:
                    st.error(str(e))
                else:
                    st.session_state["firebase_id_token"] = result.id_token
                    st.session_state["firebase_email"] = result.email or new_email
                    st.session_state["firebase_local_id"] = result.local_id or ""
                    st.rerun()

