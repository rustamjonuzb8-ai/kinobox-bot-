import os, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot import types

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
CHANNELS = ["@kanal1", "@kanal2"]  # o'zingiznikini yozing
DB = "database.json"

bot = telebot.TeleBot(TOKEN)

def load():
    try:
        with open(DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save(d):
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(d, f)

def not_joined(uid):
    res = []
    for ch in CHANNELS:
        try:
            st = bot.get_chat_member(ch, uid).status
            if st in ("left", "kicked"):
                res.append(ch)
        except Exception:
            res.append(ch)
    return res

@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(m.chat.id, "Kino kodini yozing:")

@bot.message_handler(content_types=["video"])
def add_movie(m):
    if m.from_user.id != ADMIN_ID:
        return
    db = load()
    code = str(len(db) + 101)
    db[code] = m.video.file_id
    save(db)
    bot.reply_to(m, "Saqlandi. Kod: " + code)

@bot.message_handler(content_types=["text"])
def get_movie(m):
    code = m.text.strip()
    db = load()
    if code not in db:
        return bot.reply_to(m, "Bunday kod topilmadi")
    nj = not_joined(m.from_user.id)
    if nj:
        kb = types.InlineKeyboardMarkup()
        for c in nj:
            kb.add(types.InlineKeyboardButton(c, url="https://t.me/" + c[1:]))
        kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_" + code))
        return bot.send_message(m.chat.id, "Avval kanallarga obuna bo'ling:", reply_markup=kb)
    bot.send_video(m.chat.id, db[code])

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_"))
def check(c):
    code = c.data[6:]
    if not_joined(c.from_user.id):
        return bot.answer_callback_query(c.id, "Hali obuna bo'lmadingiz!", show_alert=True)
    bot.send_video(c.message.chat.id, load()[code])

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

def web():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), H).serve_forever()

threading.Thread(target=web, daemon=True).start()
bot.infinity_polling()

