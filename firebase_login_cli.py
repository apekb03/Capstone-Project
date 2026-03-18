from __future__ import annotations

import argparse
import json
import sys

from firebase_auth import FirebaseAuthError, env_or_raise, sign_in_with_email_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Firebase email/password sign-in (prints ID token).")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument(
        "--api-key",
        default=None,
        help="Firebase Web API key (or set FIREBASE_API_KEY)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON response (includes refresh token).",
    )
    args = parser.parse_args()

    api_key = args.api_key or env_or_raise("FIREBASE_API_KEY")

    try:
        result = sign_in_with_email_password(api_key=api_key, email=args.email, password=args.password)
    except FirebaseAuthError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1)

    if args.json:
        print(json.dumps(result.raw, indent=2))
    else:
        print(result.id_token)


if __name__ == "__main__":
    main()

