import os, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot import types

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
# Majburiy obuna kanallari: Render'da CHANNELS o'zgaruvchisiga vergul bilan yozing.
# Ommaviy kanal:  @kanal1
# Yopiq kanal:    -1001234567890|https://t.me/+taklifhavolasi   (ID|havola)
def parse_channels(raw):
    res = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if item.startswith("http"):
            # Faqat havola: a'zolik tekshirilmaydi (so'rov bilan qo'shiladigan kanallar uchun)
            res.append({"id": None, "link": item})
        elif "|" in item:
            cid, link = item.split("|", 1)
            res.append({"id": int(cid.strip()), "link": link.strip()})
        else:
            res.append({"id": item, "link": "https://t.me/" + item.lstrip("@")})
    return res


CHANNELS = parse_channels(os.environ.get("CHANNELS", ""))
DB = os.environ.get("DB_PATH", "database.json")

bot = telebot.TeleBot(TOKEN)
warned = set()  # adminni bir xil xato haqida qayta-qayta bezovta qilmaslik uchun
USERS = os.environ.get("USERS_PATH", "users.json")


def load_confirmed():
    try:
        with open(USERS, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_confirmed():
    try:
        with open(USERS, "w", encoding="utf-8") as f:
            json.dump(sorted(confirmed), f)
    except Exception:
        pass


confirmed = load_confirmed()  # "Tekshirish" bosgan foydalanuvchilar (faqat havolali kanallar uchun)


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
        if ch["id"] is None:
            # Tekshirib bo'lmaydigan kanal: foydalanuvchi "Tekshirish" bosganda ishonamiz
            if uid not in confirmed:
                res.append(ch)
            continue
        try:
            st = bot.get_chat_member(ch["id"], uid).status
            if st in ("left", "kicked"):
                res.append(ch)
        except Exception as e:
            # Odatda: bot kanalda admin emas yoki kanal ID'si noto'g'ri.
            # Hamma foydalanuvchi bloklanib qolmasligi uchun kanalni o'tkazib yuboramiz
            # va adminni bir marta ogohlantiramiz.
            if ch["id"] not in warned:
                warned.add(ch["id"])
                try:
                    bot.send_message(
                        ADMIN_ID,
                        "⚠️ " + str(ch["id"]) + " kanalini tekshirib bo'lmadi: " + str(e)
                        + "\nBotni shu kanalga ADMIN qiling va ID'sini tekshiring.",
                    )
                except Exception:
                    pass
    return res


def sub_keyboard(nj, code=""):
    kb = types.InlineKeyboardMarkup()
    for ch in nj:
        n = CHANNELS.index(ch) + 1
        kb.add(types.InlineKeyboardButton("📢 " + str(n) + "-kanal", url=ch["link"]))
    kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_" + code))
    return kb


@bot.my_chat_member_handler()
def on_added(u):
    """Bot kanalga admin qilinsa, kanal ID'sini adminga yuboradi (CHANNELS uchun kerak)."""
    try:
        if u.chat.type in ("channel", "supergroup", "group") and u.new_chat_member.status == "administrator":
            bot.send_message(
                ADMIN_ID,
                "✅ Kanal: " + str(u.chat.title) + "\nID: " + str(u.chat.id)
                + "\n\nCHANNELS ga shunday yozing:\n" + str(u.chat.id) + "|<taklif_havolasi>",
            )
    except Exception:
        pass


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
        confirmed.add(c.from_user.id)
        save_confirmed()
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
