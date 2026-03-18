from __future__ import annotations

import argparse
import json
import sys

from firebase_auth import FirebaseAuthError, env_or_raise, verify_id_token


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a Firebase ID token using firebase-admin.")
    parser.add_argument(
        "--token",
        required=True,
        help="Firebase ID token (JWT) from client sign-in.",
    )
    parser.add_argument(
        "--service-account",
        default=None,
        help="Path to Firebase service account JSON (or set FIREBASE_SERVICE_ACCOUNT_JSON).",
    )
    args = parser.parse_args()

    sa_path = args.service_account or env_or_raise("FIREBASE_SERVICE_ACCOUNT_JSON")

    try:
        decoded = verify_id_token(id_token=args.token, service_account_json_path=sa_path)
    except FirebaseAuthError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1)

    print(json.dumps(decoded, indent=2))


if __name__ == "__main__":
    main()

