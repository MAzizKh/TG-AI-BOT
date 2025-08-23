import os, logging, sqlite3, json, random, string
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote as urlquote

import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# ---------- ENV ----------
load_dotenv(dotenv_path=Path(__file__).with_name('.env'))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
CALENDLY_API_TOKEN = os.getenv("CALENDLY_API_TOKEN", "").strip()
DB_PATH = os.getenv("DATABASE_PATH", "data.sqlite")
PORT = int(os.getenv("PORT", "8080"))

# ---------- Flask App ----------
app = Flask(__name__)

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

# ---------- DB ----------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            chat_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'en',
            step INTEGER DEFAULT 0,
            data TEXT DEFAULT '{}',
            created_at TEXT,
            updated_at TEXT
        );
    """)
    conn.commit()
    conn.close()

ensure_schema()

# ---------- Helpers ----------
def random_token(n=10):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))

def tg_send(chat_id, text):
    if not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        log.error(f"Telegram send failed: {e}")

# ---------- Routes ----------
@app.get("/")
def health():
    return jsonify({"ok": True, "time": datetime.now(timezone.utc).isoformat()})

@app.post(f"/telegram/webhook/{BOT_TOKEN}")
def telegram_webhook():
    update = request.get_json(force=True, silent=True) or {}
    chat_id = None

    if "message" in update:
        m = update["message"]
        chat_id = m["chat"]["id"]
        text = (m.get("text") or "").lower()

        if text in ("/start", "start", "hi", "hello", "привет", "салом"):
            tg_send(chat_id, "👋 Welcome to Silk & Shine Beauty!\nChoose your language: English / Русский / Oʻzbekcha")
        else:
            tg_send(chat_id, "✨ Please type /start to begin booking.")

    return jsonify({"ok": True})

# ---------- For Railway Local Run ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)