"""
Stream heart rate from Pulsoid via HTTPS.

Pulsoid API: https://dev.pulsoid.net/api/v1/data/heart_rate/latest
Docs: https://docs.pulsoid.net/read-heart-rate/read-latest-heart-rate-via-http

"""

import json
import os
import ssl
import sys
import time
import urllib.request

# Load .env from project directory (no extra dependency)
def _load_dotenv():
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

PULSOID_HEART_RATE_URL = "https://dev.pulsoid.net/api/v1/data/heart_rate/latest"
PULSOID_VALIDATE_URL = "https://dev.pulsoid.net/api/v1/token/validate"


def _ssl_context() -> ssl.SSLContext:
    """SSL context that works on macOS (uses certifi bundle if available)."""
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return ctx


def validate_token(access_token: str) -> tuple[bool, str | dict]:
    """
    Validate the Pulsoid access token. Returns (True, response_dict) if valid,
    or (False, error_message) if invalid or missing data:heart_rate:read scope.
    """
    req = urllib.request.Request(
        PULSOID_VALIDATE_URL,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = ""
        if e.fp:
            try:
                body = e.fp.read().decode()
            except Exception:
                pass
        if e.code == 401:
            return False, "Token is invalid or expired. Create a new one at https://pulsoid.net"
        return False, f"Token validation failed ({e.code}): {body or e.reason}"
    except urllib.error.URLError as e:
        return False, f"Request failed: {e.reason}"
    except json.JSONDecodeError as e:
        return False, f"Invalid response: {e}"
    scopes = data.get("scopes") or []
    if "data:heart_rate:read" not in scopes:
        return False, (
            f"Token is valid but missing scope 'data:heart_rate:read'. "
            f"Current scopes: {scopes}. Create a new token with heart rate read permission."
        )
    return True, data


def get_heart_rate(access_token: str, plain_only: bool = False) -> dict | int | None:
    """
    Make a single HTTPS GET request to Pulsoid and return the latest heart rate.

    Args:
        access_token: Pulsoid API access token (Bearer).
        plain_only: If True, request text/plain response (heart rate number only).

    Returns:
        With plain_only=False: {"measured_at": ms, "data": {"heart_rate": n}} or None on error.
        With plain_only=True: heart rate (int) or None on error.
        HTTP 412: no heart rate data available (returns None).
    """
    url = PULSOID_HEART_RATE_URL
    if plain_only:
        url += "?response_mode=text_plain_only_heart_rate"

    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context()) as resp:
            body = resp.read().decode()
            if plain_only:
                return int(body.strip()) if body.strip().isdigit() else None
            return json.loads(body)
    except urllib.error.HTTPError as e:
        if e.code == 412:
            return None  # No heart rate data
        print(f"HTTP error {e.code}: {e.reason}", file=sys.stderr)
        if e.fp:
            try:
                print(e.fp.read().decode(), file=sys.stderr)
            except Exception:
                pass
        return None
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"Request error: {e.reason}", file=sys.stderr)
        return None


def stream_heart_rate(
    access_token: str,
    interval_ms: int = 500,
    plain_only: bool = False,
    callback=None,
):
    """
    Poll Pulsoid every `interval_ms` and stream heart rate updates.

    Args:
        access_token: Pulsoid API access token.
        interval_ms: Time between requests (recommended 500ms for real-time).
        plain_only: Request plain heart rate number only.
        callback: Optional callable(heart_rate_data) called on each update.
    """
    interval_sec = interval_ms / 1000.0
    while True:
        result = get_heart_rate(access_token, plain_only=plain_only)
        if result is not None:
            if callback:
                callback(result)
            else:
                if plain_only:
                    print(result)
                else:
                    hr = result.get("data", {}).get("heart_rate")
                    ts = result.get("measured_at")
                    print(f"heart_rate={hr} measured_at={ts}")
        else:
            print("(no data)", file=sys.stderr)
        time.sleep(interval_sec)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Stream Pulsoid heart rate via HTTPS")
    parser.add_argument(
        "--token",
        "-t",
        default=os.environ.get("PULSOID_ACCESS_TOKEN"),
        help="Pulsoid access token (or set PULSOID_ACCESS_TOKEN)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fetch once and exit (default: stream continuously)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=500,
        metavar="MS",
        help="Poll interval in ms (default: 500)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Response: plain heart rate number only",
    )
    args = parser.parse_args()

    if not args.token:
        print("Error: Set PULSOID_ACCESS_TOKEN or pass --token", file=sys.stderr)
        sys.exit(1)

    ok, result = validate_token(args.token)
    if not ok:
        print(f"Error: {result}", file=sys.stderr)
        sys.exit(1)

    if args.once:
        result = get_heart_rate(args.token, plain_only=args.plain)
        if result is None:
            print(
                "No heart rate data. Check that Pulsoid is running and a device is connected.",
                file=sys.stderr,
            )
            sys.exit(2)
        if args.plain:
            print(result)
        else:
            print(json.dumps(result, indent=2))
        return

    # Stream continuously (default)
    print("Streaming heart rate (Ctrl+C to stop)...", file=sys.stderr)
    stream_heart_rate(
        args.token,
        interval_ms=args.interval,
        plain_only=args.plain,
    )


if __name__ == "__main__":
    main()
