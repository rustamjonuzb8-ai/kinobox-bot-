
import os
import sqlite3
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL = os.getenv("CHANNEL_USERNAME", "@your_channel")

CODE, TITLE, VIDEO = range(3)

db = sqlite3.connect("kinolar.db", check_same_thread=False)
db.execute("""
CREATE TABLE IF NOT EXISTS movies (
    code TEXT PRIMARY KEY,
    title TEXT,
    file_id TEXT
)
""")
db.commit()


async def is_subscribed(user_id, context):
    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL,
            user_id=user_id
        )
        return member.status in ("creator", "administrator", "member") or (
            member.status == "restricted" and member.is_member
        )
    except Exception:
        return False


def join_keyboard():
    channel_name = CHANNEL.lstrip("@")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📢 Kanalga a'zo bo'lish",
            url=f"https://t.me/{channel_name}"
        )],
        [InlineKeyboardButton(
            "✅ Obunani tekshirish",
            callback_data="check_sub"
        )]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not await is_subscribed(user.id, context):
        await update.message.reply_text(
            "🎬 KINOBOX BOTga xush kelibsiz!\n\n"
            "Botdan foydalanish uchun kanalimizga a'zo bo'ling.",
            reply_markup=join_keyboard()
        )
        return

    await update.message.reply_text(
        "🎬 KINOBOX BOT\n\n"
        "Kerakli kino kodini yuboring.\n"
        "Masalan: 001"
    )


async def check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if await is_subscribed(query.from_user.id, context):
        await query.edit_message_text(
            "✅ Obuna tasdiqlandi!\n\n"
            "🎬 Endi kino kodini yuboring."
        )
    else:
        await query.answer(
            "Avval kanalga a'zo bo'ling!",
            show_alert=True
        )


async def get_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_subscribed(update.effective_user.id, context):
        await update.message.reply_text(
            "Avval kanalga a'zo bo'ling.",
            reply_markup=join_keyboard()
        )
        return

    code = update.message.text.strip()

    movie = db.execute(
        "SELECT title, file_id FROM movies WHERE code=?",
        (code,)
    ).fetchone()

    if movie:
        title, file_id = movie
        await update.message.reply_video(
            video=file_id,
            caption=f"🎬 {title}\n🔢 Kod: {code}"
        )
    else:
        await update.message.reply_text(
            "❌ Bunday koddagi kino topilmadi."
        )


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    await update.message.reply_text("🔢 Kino kodini yuboring:")
    return CODE


async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["code"] = update.message.text.strip()
    await update.message.reply_text("🎬 Kino nomini yuboring:")
    return TITLE


async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text.strip()
    await update.message.reply_text("📹 Endi kino videosini yuboring:")
    return VIDEO


async def get_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video:
        await update.message.reply_text(
            "Iltimos, videoni Telegram video shaklida yuboring."
        )
        return VIDEO

    code = context.user_data["code"]
    title = context.user_data["title"]
    file_id = update.message.video.file_id

    db.execute(
        "INSERT OR REPLACE INTO movies VALUES (?, ?, ?)",
        (code, title, file_id)
    )
    db.commit()

    await update.message.reply_text(
        f"✅ Kino saqlandi!\n\n"
        f"🎬 Nomi: {title}\n"
        f"🔢 Kodi: {code}"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Amal bekor qilindi.")
    return ConversationHandler.END


def main():
    if not TOKEN or not ADMIN_ID:
        raise ValueError("BOT_TOKEN yoki ADMIN_ID sozlanmagan!")

    app = Application.builder().token(TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            VIDEO: [MessageHandler(filters.VIDEO, get_video)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_sub, pattern="^check_sub$"))
    app.add_handler(conversation)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_movie))

    print("KINOBOX BOT ishga tushdi!")
    app.run_polling()


if __name__ == "__main__":
    main()
