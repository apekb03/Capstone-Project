"""Firebase Admin: Firestore (user profiles) + Realtime Database (leaderboards under `leaderboards/`)."""

import json
import os
import ssl
import time
import urllib.error
import urllib.request

import firebase_admin
from firebase_admin import credentials, db as rtdb, firestore

import game_state

# Directory containing this module (project folder). Used so credential paths in .env are not
# resolved relative to the process cwd — running 3DrageBait.py from the repo root vs. this folder
# used to break FIREBASE_SERVICE_ACCOUNT_JSON=../firebase_key.json and similar.
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


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
						# Do not let an empty shell/IDE value block values from .env (setdefault keeps "").
						cur = os.environ.get(key)
						if cur is None or (isinstance(cur, str) and not cur.strip()):
							os.environ[key] = value
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


_load_dotenv()


def _resolve_service_account_path() -> str:
	"""Absolute path to the service account JSON (env or default next to this file)."""
	raw = (os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip().strip('"').strip("'")
	if not raw:
		return os.path.join(_PACKAGE_DIR, "firebase_key.json")
	p = os.path.expanduser(raw)
	if os.path.isabs(p):
		return os.path.normpath(p)
	return os.path.normpath(os.path.join(_PACKAGE_DIR, p))


_FIREBASE_KEY_PATH = _resolve_service_account_path()
if not os.path.isfile(_FIREBASE_KEY_PATH):
	print(
		"[firebase] ERROR: Service account JSON not found at:\n"
		f"  {_FIREBASE_KEY_PATH}\n"
		"Set FIREBASE_SERVICE_ACCOUNT_JSON in .env to an absolute path, or a path relative to the\n"
		f"  game project folder: {_PACKAGE_DIR}\n"
		"(Relative paths are not read from the shell's current working directory.)"
	)
cred = credentials.Certificate(_FIREBASE_KEY_PATH)
print(f"[firebase] Service account file: {_FIREBASE_KEY_PATH}")


def _service_account_project_id() -> str | None:
	try:
		with open(_FIREBASE_KEY_PATH, "r", encoding="utf-8") as f:
			return (json.load(f).get("project_id") or "").strip() or None
	except Exception:
		return None


def _realtime_database_url() -> str | None:
	"""Set FIREBASE_DATABASE_URL in .env to your RTDB URL from Firebase Console."""
	for key in ("FIREBASE_DATABASE_URL", "firebase_database_url"):
		raw = os.environ.get(key, "").strip().strip('"').strip("'")
		if raw:
			return raw.rstrip("/")
	pid = _service_account_project_id()
	if pid:
		# Default hostname (US). EU/multi-region DBs: paste full URL from Console → Realtime Database.
		return f"https://{pid}-default-rtdb.firebaseio.com"
	return None


_rtdb_url = _realtime_database_url()
_app_options = {}
if _rtdb_url:
	_app_options["databaseURL"] = _rtdb_url

if _rtdb_url:
	print(f"[firebase] Leaderboards → Realtime Database ({_rtdb_url})  path: leaderboards/")
else:
	print(
		"[firebase] WARNING: Realtime Database URL missing — scores will not save. "
		"Set FIREBASE_DATABASE_URL in .env (not Firestore; open Realtime Database in Console)."
	)

firebase_admin.initialize_app(cred, _app_options or None)
fs = firestore.client()


def _leaderboard_level_key(level_name: str) -> str:
	s = (level_name or "unknown").strip().replace("/", "_").replace(".", "_").replace("#", "_")
	return s[:96] if s else "unknown"


def _rtdb_leaderboard_ref(level_name: str):
	if not _rtdb_url:
		return None
	return rtdb.reference(f"leaderboards/{_leaderboard_level_key(level_name)}")


def _get_firebase_web_api_key():
	for key in ("firebase_api_key", "FIREBASE_WEB_API_KEY"):
		val = os.environ.get(key)
		if val:
			return val.strip().strip('"').strip("'")
	return None


FIREBASE_WEB_API_KEY = _get_firebase_web_api_key()


class FirebaseAuthError(Exception):
	def __init__(self, code: str):
		self.code = code
		super().__init__(code)


def _normalize_firebase_auth_code(raw: str) -> str:
	if not raw:
		return "UNKNOWN"
	s = raw.strip()
	if s.startswith("HTTP_"):
		return s[:200]
	if " : " in s:
		s = s.split(" : ", 1)[0].strip()
	elif ":\n" in s:
		s = s.split(":\n", 1)[0].strip()
	elif ": " in s:
		head, _tail = s.split(": ", 1)
		head = head.strip()
		if head and all(ch.isalnum() or ch == "_" for ch in head) and len(head) < 90:
			s = head
	if len(s) > 120:
		s = s[:120]
	return s


def friendly_auth_error(code: str, mode: str) -> str:
	code = _normalize_firebase_auth_code(code)
	common = {
		"INVALID_EMAIL": "That email address is not valid.",
		"MISSING_EMAIL": "Email is required.",
		"MISSING_PASSWORD": "Password is required.",
		"WEAK_PASSWORD": "Password is too weak (try 6+ characters).",
		"EMAIL_EXISTS": "That email is already registered. Try Login instead.",
		"OPERATION_NOT_ALLOWED": "Email/password auth is disabled in Firebase. Enable it in Firebase Console → Authentication → Sign-in method.",
		"PASSWORD_LOGIN_DISABLED": "Email/password auth is disabled in Firebase. Enable it in Firebase Console → Authentication → Sign-in method.",
		"TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Try again later.",
		"API_KEY_INVALID": "Your firebase_api_key is invalid (check `.env`).",
		"PROJECT_NOT_FOUND": "Firebase project not found for this API key.",
		"MISSING_API_KEY": "Missing firebase_api_key in `.env`.",
		"ADMIN_ONLY_OPERATION": "This project blocks public sign-up. In Firebase Console → Authentication → Settings, allow user sign-up (or use Login if you already have an account).",
		"USER_DISABLED": "This account has been disabled.",
		"DISABLED_USER": "This account has been disabled.",
	}
	if code in common:
		return common[code]
	if code.startswith("NETWORK_ERROR"):
		return "Network error talking to Firebase. Check internet / firewall / VPN."
	if code.startswith("HTTP_"):
		return f"Firebase returned {code}. Check firebase_api_key and that Identity Toolkit is enabled for this project."
	if code == "INVALID_LOGIN_CREDENTIALS":
		if mode == "signup":
			return "Signup failed. Double-check you’re on the Sign Up tab and that Email/Password auth is enabled in Firebase Console."
		return "Incorrect email or password."
	if code == "EMAIL_NOT_FOUND":
		return "No account found with that email. Try Sign Up."
	if code == "INVALID_PASSWORD":
		return "Incorrect password."
	if len(code) > 120:
		return f"Firebase: {code[:117]}..."
	return f"Firebase: {code}"


def _firebase_auth_request(endpoint: str, payload: dict):
	if not FIREBASE_WEB_API_KEY:
		raise FirebaseAuthError("MISSING_API_KEY")

	url = f"https://identitytoolkit.googleapis.com/v1/{endpoint}?key={FIREBASE_WEB_API_KEY}"
	body = json.dumps(payload).encode("utf-8")
	req = urllib.request.Request(
		url,
		data=body,
		method="POST",
		headers={"Content-Type": "application/json"},
	)
	try:
		with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
			raw = resp.read().decode("utf-8")
			return json.loads(raw)
	except urllib.error.HTTPError as err:
		body_bytes = err.read()
		try:
			text = body_bytes.decode("utf-8")
		except Exception:
			text = repr(body_bytes[:200])
		print(f"[AUTH] HTTP {err.code} body={text[:800]}")
		try:
			data = json.loads(text)
			message = ((data.get("error") or {}).get("message")) or f"HTTP_{err.code}"
		except Exception:
			message = f"HTTP_{err.code}: {text[:200]}"
		raise FirebaseAuthError(message)
	except (urllib.error.URLError, json.JSONDecodeError) as err:
		raise FirebaseAuthError(f"NETWORK_ERROR: {err}")


def firebase_sign_up(email: str, password: str):
	return _firebase_auth_request(
		"accounts:signUp",
		{"email": email, "password": password, "returnSecureToken": True},
	)


def firebase_sign_in(email: str, password: str):
	return _firebase_auth_request(
		"accounts:signInWithPassword",
		{"email": email, "password": password, "returnSecureToken": True},
	)


def upsert_user_profile(uid: str, email: str, display_name: str):
	doc = fs.collection("users").document(uid)
	doc.set(
		{
			"uid": uid,
			"email": email,
			"display_name": display_name,
			"updated_at": firestore.SERVER_TIMESTAMP,
		},
		merge=True,
	)
	return doc.get().to_dict() or {"uid": uid, "email": email, "display_name": display_name}


def get_user_profile(uid: str):
	doc = fs.collection("users").document(uid).get()
	return doc.to_dict() if doc.exists else None


def sync_user_profile_to_firestore(uid: str, email: str, display_name: str, is_signup: bool):
	fallback = {"uid": uid, "email": email, "display_name": display_name}
	try:
		if is_signup:
			upsert_user_profile(uid, email, display_name)
		profile = get_user_profile(uid) or fallback
		return profile, None
	except Exception as exc:
		import traceback

		traceback.print_exc()
		warn = (
			"Login worked, but Firestore could not save or read your profile. "
			"Enable Firestore for this Firebase project and ensure `firebase_key.json` is for the same project as `firebase_api_key`. "
			f"({type(exc).__name__})"
		)
		return fallback, warn


def submit_score(level_name, player_name, time_seconds, deaths, source=None):
	"""Append one row under Realtime Database `leaderboards/<level>/` (not Firestore).

	Returns (ok, err_message). err_message is None on success.
	"""
	ref = _rtdb_leaderboard_ref(level_name)
	if ref is None:
		msg = (
			"Realtime Database URL missing. Set FIREBASE_DATABASE_URL in .env "
			"(Console → Realtime Database → copy database URL)."
		)
		print("[leaderboard]", msg)
		return False, msg
	try:
		payload = {
			"level": level_name,
			"player": (player_name or "Player").strip()[:64],
			"time": float(round(time_seconds, 2)),
			"deaths": int(deaths),
			"ts": time.time(),
		}
		if source:
			payload["source"] = str(source)[:32]
		u = game_state.current_user
		if u and u.get("uid"):
			payload["uid"] = str(u["uid"])
		child = ref.push(payload)
		key = getattr(child, "key", None) or "?"
		print(
			f"[leaderboard] OK wrote RTDB {ref.path}/{key} "
			f"player={payload['player']} time={payload['time']}s deaths={payload['deaths']} "
			f"source={payload.get('source', '-')}"
		)
		return True, None
	except Exception as e:
		print("[leaderboard] Realtime DB submit error:", e)
		return False, f"{type(e).__name__}: {e}"


def get_top_scores(level_name, limit=40):
	ref = _rtdb_leaderboard_ref(level_name)
	if ref is None:
		return []
	try:
		data = ref.get()
		if not data or not isinstance(data, dict):
			return []
		rows: list[dict] = []
		for _key, row in data.items():
			if not isinstance(row, dict):
				continue
			try:
				t = float(row.get("time", 999999.0))
			except (TypeError, ValueError):
				t = 999999.0
			rows.append(
				{
					"player": str(row.get("player", "Player")),
					"time": t,
					"deaths": int(row.get("deaths", 0)),
					"uid": row.get("uid"),
					"level": row.get("level", level_name),
				}
			)
		rows.sort(key=lambda r: (r["time"], r["deaths"]))
		return rows[:limit]
	except Exception as e:
		print("[leaderboard] Realtime DB fetch error:", e)
		return []
