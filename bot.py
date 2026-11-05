import os, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot import types

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
# Majburiy obuna kanallari: Render'da CHANNELS o'zgaruvchisiga vergul bilan yozing,
# masalan: @kanal1,@kanal2
CHANNELS = [c.strip() for c in os.environ.get("CHANNELS", "@kanal1,@kanal2").split(",") if c.strip()]
DB = os.environ.get("DB_PATH", "database.json")

bot = telebot.TeleBot(TOKEN)
warned = set()  # adminni bir xil xato haqida qayta-qayta bezovta qilmaslik uchun


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
    """Foydalanuvchi obuna bo'lmagan kanallar ro'yxati."""
    res = []
    for ch in CHANNELS:
        try:
            st = bot.get_chat_member(ch, uid).status
            if st in ("left", "kicked"):
                res.append(ch)
        except Exception as e:
            # Odatda: bot kanalda admin emas yoki kanal nomi noto'g'ri.
            # Hamma foydalanuvchi bloklanib qolmasligi uchun kanalni o'tkazib yuboramiz
            # va adminni bir marta ogohlantiramiz.
            if ch not in warned:
                warned.add(ch)
                try:
                    bot.send_message(
                        ADMIN_ID,
                        "⚠️ " + ch + " kanalini tekshirib bo'lmadi: " + str(e)
                        + "\nBotni shu kanalga ADMIN qiling va nomini tekshiring.",
                    )
                except Exception:
                    pass
    return res


def sub_keyboard(nj, code=""):
    kb = types.InlineKeyboardMarkup()
    for c in nj:
        kb.add(types.InlineKeyboardButton("📢 " + c, url="https://t.me/" + c.lstrip("@")))
    kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_" + code))
    return kb


def ask_to_join(chat_id, nj, code=""):
    bot.send_message(
        chat_id,
        "Botdan foydalanish uchun avval kanallarga obuna bo'ling, so'ng \"Tekshirish\" tugmasini bosing:",
        reply_markup=sub_keyboard(nj, code),
    )


@bot.message_handler(commands=["start"])
def start(m):
    if m.from_user.id != ADMIN_ID:
        nj = not_joined(m.from_user.id)
        if nj:
            return ask_to_join(m.chat.id, nj)
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
    if m.from_user.id != ADMIN_ID:
        # Obuna tekshiruvi har doim birinchi: obuna bo'lmagan kodning bor-yo'qligini ham bilmaydi
        nj = not_joined(m.from_user.id)
        if nj:
            return ask_to_join(m.chat.id, nj, code)
    db = load()
    if code not in db:
        return bot.reply_to(m, "Bunday kod topilmadi")
    bot.send_video(m.chat.id, db[code])


@bot.callback_query_handler(func=lambda c: c.data.startswith("check_"))
def check(c):
    code = c.data[6:]
    if c.from_user.id != ADMIN_ID:
        nj = not_joined(c.from_user.id)
        if nj:
            return bot.answer_callback_query(c.id, "Hali hamma kanalga obuna bo'lmadingiz!", show_alert=True)
    bot.answer_callback_query(c.id, "✅ Rahmat!")
    db = load()
    if code and code in db:
        bot.send_video(c.message.chat.id, db[code])
    else:
        bot.send_message(c.message.chat.id, "Kino kodini yozing:")


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")


def web():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), H).serve_forever()


threading.Thread(target=web, daemon=True).start()
bot.infinity_polling()
