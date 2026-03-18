## Firebase login (Python)

This repo currently uses plain Python scripts. Firebase Auth normally signs users in on the client (web/mobile) and your backend verifies the ID token.

### Option A: Python "frontend" (Streamlit UI)

1) Set `FIREBASE_API_KEY` in `.env`

2) Run:

```bash
cd Capstone-Project
uv run streamlit run streamlit_login_app.py
```

## Firebase Realtime Database leaderboard (Python)

### 1) Create a Realtime Database

In Firebase console → **Realtime Database** → Create database.

### 2) Add env vars

In `Capstone-Project/.env` add:

- `FIREBASE_SERVICE_ACCOUNT_JSON=/absolute/path/to/serviceAccountKey.json`
- `FIREBASE_DATABASE_URL=https://YOUR_PROJECT_ID-default-rtdb.firebaseio.com`

### 3) Use it in the Streamlit app

After you log in, you can:

- Submit a score (saves your **bestScore** under `/leaderboard/users/{uid}`)
- View the Top N leaderboard

### 1) Add env vars

In `Capstone-Project/.env` add:

- `FIREBASE_API_KEY=...` (from Firebase console → Project settings → General → Web API Key)
- `FIREBASE_SERVICE_ACCOUNT_JSON=/absolute/path/to/serviceAccountKey.json`

### 2) Install dependencies

If you use `uv`:

```bash
cd Capstone-Project
uv sync
```

### 3) Sign in (email/password)

```bash
cd Capstone-Project
python firebase_login_cli.py --email "you@example.com" --password "your-password"
```

This prints an **ID token**.

### 4) Verify token (server-side)

```bash
cd Capstone-Project
python firebase_verify_cli.py --token "<PASTE_ID_TOKEN_HERE>"
```

If valid, it prints the decoded claims (includes `uid`, and sometimes `email`).
