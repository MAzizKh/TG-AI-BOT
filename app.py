import os
import logging
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# ---------- ENV ----------
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
CALENDLY_API_TOKEN = os.getenv("CALENDLY_API_TOKEN")

# ---------- Flask ----------
app = Flask(__name__)

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

# ---------- State (in-memory for demo, use DB in prod) ----------
sessions = {}

# ---------- Helpers ----------
def tg_send(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)

def tg_keyboard(buttons):
    return {"keyboard": buttons, "resize_keyboard": True, "one_time_keyboard": True}

def tg_inline(buttons):
    return {"inline_keyboard": buttons}

# ---------- Calendly Helpers ----------
CALENDLY_BASE = "https://api.calendly.com"

def get_calendly_event_type():
    url = f"{CALENDLY_BASE}/event_types"
    headers = {"Authorization": f"Bearer {CALENDLY_API_TOKEN}"}
    r = requests.get(url, headers=headers).json()
    items = r.get("collection", [])
    if not items:
        return None
    return items[0]["uri"]

def get_calendly_slots(event_type):
    url = f"{CALENDLY_BASE}/event_type_available_times"
    headers = {"Authorization": f"Bearer {CALENDLY_API_TOKEN}"}
    params = {"event_type": event_type}
    r = requests.get(url, headers=headers).json()
    slots = []
    for item in r.get("collection", [])[:3]:
        slots.append(item["start_time"])
    return slots

def book_calendly_slot(event_type, name, phone, slot):
    url = f"{CALENDLY_BASE}/scheduled_events"
    headers = {
        "Authorization": f"Bearer {CALENDLY_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "event_type": event_type,
        "invitee": {"name": name, "email": f"{phone}@fake.com"},  # Calendly needs "email", so fake it
        "start_time": slot
    }
    r = requests.post(url, headers=headers, json=data)
    return r.ok

# ---------- Localized Texts ----------
TEXTS = {
    "en": {
        "welcome": "👋 Welcome! Choose your language:",
        "menu": "Please choose:",
        "about": "ℹ️ We are Silk & Shine Beauty — making you glow ✨",
        "ask_name": "What is your <b>Name</b>?",
        "ask_surname": "What is your <b>Surname</b>?",
        "ask_phone": "Please provide your <b>Phone Number</b>:",
        "choose_slot": "Choose a time:",
        "booked": "✅ Your appointment is booked for {}",
        "fail": "❌ Failed to book appointment."
    },
    "ru": {
        "welcome": "👋 Добро пожаловать! Выберите язык:",
        "menu": "Пожалуйста, выберите:",
        "about": "ℹ️ Мы Silk & Shine Beauty — делаем вас сияющими ✨",
        "ask_name": "Введите ваше <b>Имя</b>:",
        "ask_surname": "Введите вашу <b>Фамилию</b>:",
        "ask_phone": "Введите ваш <b>Номер телефона</b>:",
        "choose_slot": "Выберите время:",
        "booked": "✅ Ваша запись подтверждена на {}",
        "fail": "❌ Не удалось забронировать запись."
    },
    "uz": {
        "welcome": "👋 Xush kelibsiz! Tilni tanlang:",
        "menu": "Iltimos, tanlang:",
        "about": "ℹ️ Biz Silk & Shine Beauty — sizni yanada goʻzal qilamiz ✨",
        "ask_name": "Ismingizni kiriting:",
        "ask_surname": "Familiyangizni kiriting:",
        "ask_phone": "Telefon raqamingizni kiriting:",
        "choose_slot": "Vaqtni tanlang:",
        "booked": "✅ Sizning uchrashuvingiz {} ga belgilandi",
        "fail": "❌ Uchrashuvni bron qilishda xatolik yuz berdi."
    }
}

# ---------- Routes ----------
@app.get("/")
def health():
    return jsonify(ok=True)

@app.post(f"/telegram/webhook/{BOT_TOKEN}")
def telegram_webhook():
    update = request.get_json(force=True)
    chat_id = update.get("message", {}).get("chat", {}).get("id")
    text = update.get("message", {}).get("text", "")

    session = sessions.get(chat_id, {"lang": None, "step": 0, "data": {}})

    # Start
    if text == "/start":
        tg_send(chat_id, TEXTS["en"]["welcome"],
                tg_keyboard([["English"], ["Русский"], ["Oʻzbekcha"]]))
        return jsonify(ok=True)

    # Language choice
    if text in ["English", "Русский", "Oʻzbekcha"]:
        lang = "en" if text == "English" else "ru" if text == "Русский" else "uz"
        session["lang"] = lang
        session["step"] = 0
        sessions[chat_id] = session
        tg_send(chat_id, TEXTS[lang]["menu"],
                tg_keyboard([["📖 About Us" if lang=="en" else "📖 О нас" if lang=="ru" else "📖 Biz haqimizda"],
                             ["📅 Book Appointment" if lang=="en" else "📅 Записаться" if lang=="ru" else "📅 Uchrashuvni bron qilish"]]))
        return jsonify(ok=True)

    lang = session.get("lang", "en")
    if not lang:
        return jsonify(ok=True)

    # About Us
    if text in ["📖 About Us", "📖 О нас", "📖 Biz haqimizda"]:
        tg_send(chat_id, TEXTS[lang]["about"])
        return jsonify(ok=True)

    # Book flow
    if text in ["📅 Book Appointment", "📅 Записаться", "📅 Uchrashuvni bron qilish"]:
        session["step"] = 1
        tg_send(chat_id, TEXTS[lang]["ask_name"])
        sessions[chat_id] = session
        return jsonify(ok=True)

    # Step 1: Name
    if session["step"] == 1:
        session["data"]["name"] = text
        session["step"] = 2
        tg_send(chat_id, TEXTS[lang]["ask_surname"])
        sessions[chat_id] = session
        return jsonify(ok=True)

    # Step 2: Surname
    if session["step"] == 2:
        session["data"]["surname"] = text
        session["step"] = 3
        tg_send(chat_id, TEXTS[lang]["ask_phone"])
        sessions[chat_id] = session
        return jsonify(ok=True)

    # Step 3: Phone
    if session["step"] == 3:
        session["data"]["phone"] = text
        event_type = get_calendly_event_type()
        slots = get_calendly_slots(event_type)
        if not slots:
            tg_send(chat_id, TEXTS[lang]["fail"])
            return jsonify(ok=True)
        buttons = [[{"text": s, "callback_data": f"BOOK|{event_type}|{session['data']['name']}|{session['data']['phone']}|{s}"}] for s in slots]
        tg_send(chat_id, TEXTS[lang]["choose_slot"], {"inline_keyboard": buttons})
        session["step"] = 4
        sessions[chat_id] = session
        return jsonify(ok=True)

    return jsonify(ok=True)

@app.post(f"/telegram/callback/{BOT_TOKEN}")
def telegram_callback():
    update = request.get_json(force=True)
    cb = update.get("callback_query", {})
    data = cb.get("data", "")
    chat_id = cb.get("message", {}).get("chat", {}).get("id")
    session = sessions.get(chat_id, {"lang": "en"})
    lang = session["lang"]

    if data.startswith("BOOK|"):
        _, event_type, name, phone, slot = data.split("|")
        ok = book_calendly_slot(event_type, name, phone, slot)
        if ok:
            tg_send(chat_id, TEXTS[lang]["booked"].format(slot))
        else:
            tg_send(chat_id, TEXTS[lang]["fail"])
    return jsonify(ok=True)

# ---------- Run ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)