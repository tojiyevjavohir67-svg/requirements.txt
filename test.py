import os
import threading
from flask import Flask
import telebot
from telebot import types
from pymongo import MongoClient

TOKEN = "8650420595:AAGsWFJX-mYCGWUPI0UltoxG0KK6Q-X4n6c"
ADMIN_ID = 6968399046
MONGO_URL = "mongodb+srv://tojiyevjavohir67_db_user:jtwASN46W0zU9sw7@cluster0.pysrg0q.mongodb.net/?appName=Cluster0"

CHANNELS = [
    "@clc_kino"
]

bot = telebot.TeleBot(TOKEN)

client = MongoClient(MONGO_URL)
db = client["kino_bot"]
movies = db["movies"]
users = db["users"]

admin_states = {}

app = Flask(__name__)


def is_admin(user_id):
    return int(user_id) == int(ADMIN_ID)


def save_user(message):
    user = message.from_user
    if not user:
        return

    users.update_one(
        {"user_id": user.id},
        {
            "$set": {
                "user_id": user.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username or "",
            }
        },
        upsert=True
    )


def check_subscription(user_id):
    if is_admin(user_id):
        return True

    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            print("SUB STATUS:", user_id, channel, member.status)

            if member.status in ["left", "kicked"]:
                return False

        except Exception as e:
            print("OBUNA TEKSHIRISH XATOSI:", e)
            return False

    return True


def subscribe_keyboard():
    markup = types.InlineKeyboardMarkup()

    for channel in CHANNELS:
        markup.add(
            types.InlineKeyboardButton(
                text=f"📢 Obuna bo'lish: {channel}",
                url=f"https://t.me/{channel.replace('@', '')}"
            )
        )

    markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    return markup


def admin_panel():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Kino qo'shish", callback_data="add_movie"))
    markup.add(types.InlineKeyboardButton("🗑 Kino o'chirish", callback_data="delete_movie"))
    markup.add(types.InlineKeyboardButton("🎬 Kinolar ro'yxati", callback_data="movie_list"))
    markup.add(types.InlineKeyboardButton("📊 Statistika", callback_data="stats"))
    return markup


def send_admin_panel(chat_id):
    bot.send_message(
        chat_id,
        "👨‍💻 Admin panel:",
        reply_markup=admin_panel()
    )


@bot.message_handler(commands=["start"])
def start(message):
    print("START BOSILDI:", message.from_user.id)
    save_user(message)

    user_id = message.from_user.id

    if is_admin(user_id):
        send_admin_panel(message.chat.id)
        return

    if not check_subscription(user_id):
        bot.send_message(
            message.chat.id,
            "🔒 Botdan foydalanish uchun avval kanalga obuna bo'ling!\n\n"
            "📢 Kanalga obuna bo'ling va ✅ Tekshirish tugmasini bosing.",
            reply_markup=subscribe_keyboard()
        )
        return

    bot.send_message(
        message.chat.id,
        "🎬 Xush kelibsiz!\n\n🔢 Kino kodini yuboring."
    )


@bot.message_handler(commands=["admin"])
def admin_command(message):
    if is_admin(message.from_user.id):
        send_admin_panel(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub(call):
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
        bot.send_message(
            call.message.chat.id,
            "✅ Obuna tasdiqlandi!\n\n🎬 Endi kino kodini yuboring."
        )
    else:
        bot.answer_callback_query(call.id, "❌ Hali obuna bo'lmagansiz!")
        bot.send_message(
            call.message.chat.id,
            "❌ Siz hali kanalga obuna bo'lmagansiz.\n\n📢 Avval kanalga obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )


@bot.callback_query_handler(func=lambda call: call.data == "add_movie")
def add_movie(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)
    admin_states[call.from_user.id] = {"step": "waiting_code"}

    bot.send_message(
        call.message.chat.id,
        "➕ Kino qo'shish boshlandi.\n\n🔢 Kino kodini yuboring. Masalan: 1"
    )


@bot.callback_query_handler(func=lambda call: call.data == "delete_movie")
def delete_movie(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)
    admin_states[call.from_user.id] = {"step": "delete_code"}

    bot.send_message(
        call.message.chat.id,
        "🗑 O'chirmoqchi bo'lgan kino kodini yuboring:"
    )


@bot.callback_query_handler(func=lambda call: call.data == "movie_list")
def movie_list(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)

    all_movies = list(movies.find().sort("_id", -1).limit(100))

    if not all_movies:
        bot.send_message(call.message.chat.id, "📭 Hozircha kinolar yo'q.", reply_markup=admin_panel())
        return

    text = "🎬 Kinolar ro'yxati:\n\n"

    for i, movie in enumerate(all_movies, start=1):
        text += f"{i}. 🔢 Kod: {movie.get('code')}\n"
        text += f"🎞 Nomi: {movie.get('caption', 'Nomsiz')}\n\n"

    if len(text) > 4000:
        text = text[:4000] + "\n\n..."

    bot.send_message(call.message.chat.id, text, reply_markup=admin_panel())


@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)

    users_count = users.count_documents({})
    movies_count = movies.count_documents({})

    bot.send_message(
        call.message.chat.id,
        "📊 Bot statistikasi:\n\n"
        f"👥 Start bosgan odamlar: {users_count}\n"
        f"🎬 Kinolar soni: {movies_count}",
        reply_markup=admin_panel()
    )


@bot.message_handler(content_types=["video"])
def handle_video(message):
    user_id = message.from_user.id

    if not is_admin(user_id):
        return

    state = admin_states.get(user_id)

    if not state or state.get("step") != "waiting_video":
        bot.send_message(
            message.chat.id,
            "⚠️ Video qo'shish uchun avval ➕ Kino qo'shish tugmasini bosing."
        )
        return

    code = state.get("code")
    caption = message.caption or f"🎬 Kino\n🔢 Kod: {code}"

    movies.update_one(
        {"code": code},
        {
            "$set": {
                "code": code,
                "file_id": message.video.file_id,
                "caption": caption
            }
        },
        upsert=True
    )

    admin_states.pop(user_id, None)

    bot.send_message(
        message.chat.id,
        f"✅ Kino saqlandi!\n\n🔢 Kod: {code}",
        reply_markup=admin_panel()
    )


@bot.message_handler(content_types=["text"])
def handle_text(message):
    print("TEXT KELDI:", message.from_user.id, message.text)
    save_user(message)

    user_id = message.from_user.id
    text = (message.text or "").strip()

    if is_admin(user_id):
        state = admin_states.get(user_id)

        if state:
            if state.get("step") == "waiting_code":
                if not text.isdigit():
                    bot.send_message(message.chat.id, "❌ Kod faqat raqam bo'lishi kerak. Masalan: 1")
                    return

                admin_states[user_id] = {
                    "step": "waiting_video",
                    "code": text
                }

                bot.send_message(
                    message.chat.id,
                    f"✅ Kod qabul qilindi: {text}\n\n🎥 Endi video yuboring:"
                )
                return

            if state.get("step") == "delete_code":
                result = movies.delete_one({"code": text})
                admin_states.pop(user_id, None)

                if result.deleted_count:
                    bot.send_message(message.chat.id, f"✅ Kino o'chirildi!\n\n🔢 Kod: {text}", reply_markup=admin_panel())
                else:
                    bot.send_message(message.chat.id, "❌ Bunday kodli kino topilmadi.", reply_markup=admin_panel())
                return

        if text.isdigit():
            movie = movies.find_one({"code": text})

            if movie:
                bot.send_video(
                    message.chat.id,
                    movie["file_id"],
                    caption=movie.get("caption", "")
                )
            else:
                bot.send_message(message.chat.id, "😕 Bu kod bo'yicha kino topilmadi.", reply_markup=admin_panel())
            return

        send_admin_panel(message.chat.id)
        return

    if not check_subscription(user_id):
        bot.send_message(
            message.chat.id,
            "🔒 Botdan foydalanish uchun kanalga obuna bo'lishingiz kerak!\n\n"
            "📢 Avval kanalga obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )
        return

    if not text.isdigit():
        bot.send_message(
            message.chat.id,
            "❌ Noto'g'ri kod.\n\n🔢 Kino kodini raqam bilan yuboring."
        )
        return

    movie = movies.find_one({"code": text})

    if not movie:
        bot.send_message(
            message.chat.id,
            "😕 Bu kod bo'yicha kino topilmadi.\n\n🔢 Kodni tekshirib qayta yuboring."
        )
        return

    bot.send_video(
        message.chat.id,
        movie["file_id"],
        caption=movie.get("caption", "")
    )


@app.route("/", methods=["GET"])
def home():
    return "✅ Kino bot ishlayapti", 200


def run_bot():
    print("✅ Bot ishga tushmoqda...")

    try:
        bot.remove_webhook()
        print("✅ Webhook o'chirildi")
    except Exception as e:
        print("Webhook xatosi:", e)

    bot.infinity_polling(
        timeout=60,
        long_polling_timeout=60,
        skip_pending=True
    )


if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=False)
