import os
import uuid
import time
import json
import threading
from flask import Flask
import telebot
from pymongo import MongoClient

TOKEN = "8650420595:AAGsWFJX-mYCGWUPI0UltoxG0KK6Q-X4n6c"
ADMIN_ID =  6968399046
MONGO_URL = "mongodb+srv://tojiyevjavohir67_db_user:jtwASN46W0zU9sw7@cluster0.pysrg0q.mongodb.net/?appName=Cluster0"

KINO_KODLARI_URL = "https://t.me/clc_kino"

# Premium emoji ID larni shu yerga qo'yasiz.
# Bilmasangiz bo'sh qoldiring: ""
PREMIUM_EMOJI_IDS = {
    "add": "5030787243543888610",
    "delete": "5271851165024271824",
    "list": "5233585291339536488",
    "stats": "5233308575186591026",
    "channel": "5195028614009103813",
    "check": "5195424863396862786",
    "broadcast": "5461054558996282111",
    "movie": "5375464961822695044",
}

bot = telebot.TeleBot(TOKEN)

client = MongoClient(MONGO_URL)
db = client["kino_bot"]

movies = db["movies"]
users = db["users"]
required_links = db["required_links"]
join_requests = db["join_requests"]

admin_states = {}
app = Flask(__name__)


def make_button(text, callback_data=None, url=None, style=None, emoji_key=None):
    btn = {"text": text}

    emoji_id = PREMIUM_EMOJI_IDS.get(emoji_key or "", "")
    if emoji_id:
        btn["icon_custom_emoji_id"] = emoji_id

    if callback_data:
        btn["callback_data"] = callback_data

    if url:
        btn["url"] = url

    if style:
        btn["style"] = style

    return btn


def make_keyboard(rows):
    return json.dumps({"inline_keyboard": rows})


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

    for item in required_links.find():
        link_type = item.get("type")
        username = item.get("username")

        if link_type in ["telegram", "chat"]:
            try:
                member = bot.get_chat_member(username, user_id)
                if member.status in ["left", "kicked"]:
                    return False
            except Exception as e:
                print("OBUNA TEKSHIRISH XATOSI:", e)
                return False

        if link_type == "request_channel":
            try:
                member = bot.get_chat_member(username, user_id)
                if member.status not in ["left", "kicked"]:
                    continue
            except Exception:
                pass

            request_exists = join_requests.find_one({
                "user_id": user_id,
                "username": username
            })

            if not request_exists:
                return False

    return True


def subscribe_keyboard():
    rows = []

    for item in required_links.find().sort("_id", 1):
        title = item.get("title", "Obuna")
        url = item.get("url", "")
        link_type = item.get("type", "telegram")

        if link_type == "telegram":
            icon = "📢"
        elif link_type == "chat":
            icon = "💬"
        elif link_type == "request_channel":
            icon = "📝"
        elif link_type == "instagram":
            icon = "📸"
        else:
            icon = "🔗"

        rows.append([
            make_button(
                f"{icon} Qo'shilish: {title}",
                url=url,
                style="primary",
                emoji_key="channel"
            )
        ])

    rows.append([
        make_button("✅ Tekshirish", callback_data="check_sub", style="success", emoji_key="check")
    ])

    return make_keyboard(rows)


def user_start_keyboard():
    return make_keyboard([
        [
            make_button(
                "🎬 KINO KODLARI",
                url=KINO_KODLARI_URL,
                style="primary",
                emoji_key="movie"
            )
        ]
    ])


def admin_panel():
    return make_keyboard([
        [make_button("➕ Kino qo'shish", callback_data="add_movie", style="success", emoji_key="add")],
        [make_button("🗑 Kino o'chirish", callback_data="delete_movie", style="danger", emoji_key="delete")],
        [make_button("🎬 Kinolar ro'yxati", callback_data="movie_list", style="primary", emoji_key="list")],
        [make_button("📊 Statistika", callback_data="stats", style="primary", emoji_key="stats")],
        [make_button("📢 Majburiy kanal/chat qo'shish", callback_data="add_required", style="success", emoji_key="channel")],
        [make_button("📋 Majburiy obunalar", callback_data="required_list", style="primary", emoji_key="list")],
        [make_button("➖ Majburiy obunani o'chirish", callback_data="delete_required", style="danger", emoji_key="delete")],
        [make_button("📨 Hammaga xabar yuborish", callback_data="broadcast", style="success", emoji_key="broadcast")]
    ])


def send_admin_panel(chat_id):
    bot.send_message(
        chat_id,
        "💎👨‍💻 Admin panel:\n\nKerakli bo'limni tanlang:",
        reply_markup=admin_panel()
    )


def send_user_start(chat_id):
    bot.send_message(
        chat_id,
        "💎🎬 Xush kelibsiz!\n\n🔢 Kino kodini yuboring.",
        reply_markup=user_start_keyboard()
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
            "💎🔒 Botdan foydalanish uchun avval majburiy obunalarga qo'shiling!\n\n"
            "✅ Keyin tekshirish tugmasini bosing.",
            reply_markup=subscribe_keyboard()
        )
        return

    send_user_start(message.chat.id)


@bot.message_handler(commands=["admin", "panel"])
def admin_command(message):
    if is_admin(message.from_user.id):
        send_admin_panel(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub(call):
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
        bot.send_message(
            call.message.chat.id,
            "✅ Obuna tasdiqlandi!\n\n🎬 Endi kino kodini yuboring.",
            reply_markup=user_start_keyboard()
        )
    else:
        bot.answer_callback_query(call.id, "❌ Hali obuna bo'lmagansiz!")
        bot.send_message(
            call.message.chat.id,
            "❌ Siz hali majburiy obunalarga qo'shilmagansiz.\n\n📢 Avval obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )


@bot.chat_join_request_handler()
def join_request(update):
    user = update.from_user
    chat = update.chat
    username = f"@{chat.username}" if chat.username else str(chat.id)

    join_requests.update_one(
        {"user_id": user.id, "username": username},
        {
            "$set": {
                "user_id": user.id,
                "username": username,
                "chat_id": chat.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
            }
        },
        upsert=True
    )

    try:
        bot.approve_chat_join_request(chat.id, user.id)
    except Exception as e:
        print("Zayafka approve xatosi:", e)


@bot.callback_query_handler(func=lambda call: call.data == "add_movie")
def add_movie(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)
    admin_states[call.from_user.id] = {"step": "waiting_code"}
    bot.send_message(call.message.chat.id, "➕ Kino qo'shish boshlandi.\n\n🔢 Kino kodini yuboring. Masalan: 1")


@bot.callback_query_handler(func=lambda call: call.data == "delete_movie")
def delete_movie(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)
    admin_states[call.from_user.id] = {"step": "delete_code"}
    bot.send_message(call.message.chat.id, "🗑 O'chirmoqchi bo'lgan kino kodini yuboring:")


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

    bot.send_message(call.message.chat.id, text[:4000], reply_markup=admin_panel())


@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "📊 Bot statistikasi:\n\n"
        f"👥 Start bosgan odamlar: {users.count_documents({})}\n"
        f"🎬 Kinolar soni: {movies.count_documents({})}\n"
        f"📢 Majburiy obunalar: {required_links.count_documents({})}",
        reply_markup=admin_panel()
    )


@bot.callback_query_handler(func=lambda call: call.data == "add_required")
def add_required(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)

    markup = make_keyboard([
        [make_button("📢 Oddiy kanal", callback_data="add_req_telegram", style="primary", emoji_key="channel")],
        [make_button("💬 Public chat/guruh", callback_data="add_req_chat", style="success", emoji_key="channel")],
        [make_button("📝 Zayafka kanal", callback_data="add_req_request", style="success", emoji_key="channel")],
        [make_button("📸 Instagram", callback_data="add_req_instagram", style="primary", emoji_key="channel")]
    ])

    bot.send_message(call.message.chat.id, "Qanday majburiy obuna qo'shasiz?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ["add_req_telegram", "add_req_chat", "add_req_request", "add_req_instagram"])
def add_required_type(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    type_map = {
        "add_req_telegram": "telegram",
        "add_req_chat": "chat",
        "add_req_request": "request_channel",
        "add_req_instagram": "instagram"
    }

    admin_states[call.from_user.id] = {
        "step": "required_title",
        "type": type_map[call.data]
    }

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📌 Obuna nomini yuboring. Masalan: Kino kanal")


@bot.callback_query_handler(func=lambda call: call.data == "required_list")
def required_list(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)

    items = list(required_links.find().sort("_id", 1))

    if not items:
        bot.send_message(call.message.chat.id, "📭 Majburiy obuna yo'q.", reply_markup=admin_panel())
        return

    text = "📋 Majburiy obunalar:\n\n"
    for item in items:
        text += f"🆔 ID: {item.get('link_id')}\n"
        text += f"📌 Nomi: {item.get('title')}\n"
        text += f"📎 Turi: {item.get('type')}\n"
        text += f"👤 Username: {item.get('username', '-')}\n"
        text += f"🔗 Link: {item.get('url')}\n\n"

    bot.send_message(call.message.chat.id, text[:4000], reply_markup=admin_panel())


@bot.callback_query_handler(func=lambda call: call.data == "delete_required")
def delete_required(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)
    admin_states[call.from_user.id] = {"step": "delete_required"}
    bot.send_message(call.message.chat.id, "➖ O'chirmoqchi bo'lgan majburiy obuna ID sini yuboring.")


@bot.callback_query_handler(func=lambda call: call.data == "broadcast")
def broadcast(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)
    admin_states[call.from_user.id] = {"step": "broadcast"}
    bot.send_message(call.message.chat.id, "📨 Hammaga yuboriladigan xabarni yozing:")


@bot.message_handler(content_types=["video"])
def handle_video(message):
    user_id = message.from_user.id

    if not is_admin(user_id):
        return

    state = admin_states.get(user_id)

    if not state or state.get("step") != "waiting_video":
        bot.send_message(message.chat.id, "⚠️ Video qo'shish uchun avval ➕ Kino qo'shish tugmasini bosing.")
        return

    code = state.get("code")
    caption = message.caption or f"🎬 Kino\n🔢 Kod: {code}"

    movies.update_one(
        {"code": code},
        {"$set": {"code": code, "file_id": message.video.file_id, "caption": caption}},
        upsert=True
    )

    admin_states.pop(user_id, None)
    bot.send_message(message.chat.id, f"✅ Kino saqlandi!\n\n🔢 Kod: {code}", reply_markup=admin_panel())


@bot.message_handler(content_types=["text"])
def handle_text(message):
    print("TEXT KELDI:", message.from_user.id, message.text)
    save_user(message)

    user_id = message.from_user.id
    text = (message.text or "").strip()

    if is_admin(user_id):
        state = admin_states.get(user_id)

        if state:
            step = state.get("step")

            if step == "waiting_code":
                if not text.isdigit():
                    bot.send_message(message.chat.id, "❌ Kod faqat raqam bo'lishi kerak. Masalan: 1")
                    return

                admin_states[user_id] = {"step": "waiting_video", "code": text}
                bot.send_message(message.chat.id, f"✅ Kod qabul qilindi: {text}\n\n🎥 Endi video yuboring:")
                return

            if step == "delete_code":
                result = movies.delete_one({"code": text})
                admin_states.pop(user_id, None)

                if result.deleted_count:
                    bot.send_message(message.chat.id, f"✅ Kino o'chirildi!\n\n🔢 Kod: {text}", reply_markup=admin_panel())
                else:
                    bot.send_message(message.chat.id, "❌ Bunday kodli kino topilmadi.", reply_markup=admin_panel())
                return

            if step == "required_title":
                admin_states[user_id]["title"] = text
                admin_states[user_id]["step"] = "required_value"

                if state.get("type") == "instagram":
                    bot.send_message(message.chat.id, "📸 Instagram link yuboring. Masalan: https://instagram.com/username")
                else:
                    bot.send_message(message.chat.id, "👤 Username yuboring. Masalan: @kanal_username")
                return

            if step == "required_value":
                link_type = state.get("type")
                title = state.get("title")
                link_id = uuid.uuid4().hex[:8]

                if link_type == "instagram":
                    username = ""
                    url = text.strip()
                else:
                    username = text.strip()
                    if not username.startswith("@"):
                        username = "@" + username
                    url = f"https://t.me/{username.replace('@', '')}"

                required_links.insert_one({
                    "link_id": link_id,
                    "title": title,
                    "type": link_type,
                    "username": username,
                    "url": url,
                    "required": True
                })

                admin_states.pop(user_id, None)

                bot.send_message(
                    message.chat.id,
                    "✅ Majburiy obuna qo'shildi!\n\n"
                    f"🆔 ID: {link_id}\n"
                    f"📌 Nomi: {title}\n"
                    f"📎 Turi: {link_type}\n"
                    f"🔗 Link: {url}",
                    reply_markup=admin_panel()
                )
                return

            if step == "delete_required":
                result = required_links.delete_one({"link_id": text})
                admin_states.pop(user_id, None)

                if result.deleted_count:
                    bot.send_message(message.chat.id, "✅ Majburiy obuna o'chirildi.", reply_markup=admin_panel())
                else:
                    bot.send_message(message.chat.id, "❌ Bunday ID topilmadi.", reply_markup=admin_panel())
                return

            if step == "broadcast":
                admin_states.pop(user_id, None)

                success = 0
                failed = 0

                for user in users.find():
                    try:
                        bot.send_message(user["user_id"], text)
                        success += 1
                        time.sleep(0.05)
                    except Exception:
                        failed += 1

                bot.send_message(
                    message.chat.id,
                    f"📨 Xabar yuborildi!\n\n✅ Yetib bordi: {success}\n❌ Xato: {failed}",
                    reply_markup=admin_panel()
                )
                return

        if text.isdigit():
            movie = movies.find_one({"code": text})

            if movie:
                bot.send_video(message.chat.id, movie["file_id"], caption=movie.get("caption", ""))
            else:
                bot.send_message(message.chat.id, "😕 Bu kod bo'yicha kino topilmadi.", reply_markup=admin_panel())
            return

        send_admin_panel(message.chat.id)
        return

    if not check_subscription(user_id):
        bot.send_message(
            message.chat.id,
            "💎🔒 Botdan foydalanish uchun avval majburiy obunalarga qo'shiling!",
            reply_markup=subscribe_keyboard()
        )
        return

    if not text.isdigit():
        bot.send_message(message.chat.id, "❌ Noto'g'ri kod.\n\n🔢 Kino kodini raqam bilan yuboring.")
        return

    movie = movies.find_one({"code": text})

    if not movie:
        bot.send_message(message.chat.id, "😕 Bu kod bo'yicha kino topilmadi.\n\n🔢 Kodni tekshirib qayta yuboring.")
        return

    bot.send_video(message.chat.id, movie["file_id"], caption=movie.get("caption", ""))


@app.route("/", methods=["GET"])
def home():
    return "✅ Kino bot ishlayapti", 200


def run_bot():
    print("✅ Bot ishga tushmoqda...")

    while True:
        try:
            bot.remove_webhook()
            print("✅ Webhook o'chirildi")

            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                skip_pending=True
            )

        except Exception as e:
            print("❌ Bot polling xatosi:", e)
            print("🔁 Bot 5 soniyadan keyin qayta ishga tushadi...")
            time.sleep(5)


if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=False)
