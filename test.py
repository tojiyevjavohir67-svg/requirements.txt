import os
import uuid
import threading
import time
from flask import Flask
import telebot
from telebot import types
from pymongo import MongoClient
import uuid
import json
import time



TOKEN = "8650420595:AAGsWFJX-mYCGWUPI0UltoxG0KK6Q-X4n6c"
ADMIN_ID = 6968399046
MONGO_URL = "mongodb+srv://tojiyevjavohir67_db_user:jtwASN46W0zU9sw7@cluster0.pysrg0q.mongodb.net/?appName=Cluster0"

DEFAULT_REQUIRED_LINKS = [
    {
        "title": "Kino kanal",
        "type": "telegram",
        "username": "@clc_kino",
        "url": "https://t.me/clc_kino",
        "required": True
    },
    {
        "title": "Kino chat",
        "type": "chat",
        "username": "@clc_chat",
        "url": "https://t.me/clc_chat",
        "required": True
    }
]

bot = telebot.TeleBot(TOKEN)

client = MongoClient(MONGO_URL)
db = client["kino_bot"]

movies = db["movies"]
users = db["users"]
links = db["required_links"]
required_links = db["required_links"]
join_requests = db["join_requests"]


admin_states = {}
app = Flask(__name__)
def button(text, callback_data=None, url=None, style=None):
    data = {"text": text}

    if callback_data:
        data["callback_data"] = callback_data

    if url:
        data["url"] = url

    if style:
        data["style"] = style

    return data


def keyboard(rows):
    return json.dumps({"inline_keyboard": rows})



def is_admin(user_id):
    return int(user_id) == int(ADMIN_ID)


def seed_default_links():
    if links.count_documents({}) == 0:
        for item in DEFAULT_REQUIRED_LINKS:
            if "kanal_username" in item["username"] or "chat_username" in item["username"]:
                continue

            item["link_id"] = uuid.uuid4().hex[:8]
            links.insert_one(item)


seed_default_links()


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


def get_required_links():
    return list(links.find().sort("_id", 1))


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

            except:
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
        rows.append([
            button(
                f"📢 Qo'shilish: {item.get('title')}",
                url=item.get("url"),
                style="primary"
            )
        ])

    rows.append([button("✅ Tekshirish", callback_data="check_sub", style="success")])

    return keyboard(rows)


        markup.add(
            types.InlineKeyboardButton(
                text=f"{icon} Qo'shilish: {title}",
                url=url
            )
        )


    return markup


def admin_panel():
    return keyboard([
        [button("➕ Kino qo'shish", callback_data="add_movie", style="success")],
        [button("🗑 Kino o'chirish", callback_data="delete_movie", style="danger")],
        [button("🎬 Kinolar ro'yxati", callback_data="movie_list", style="primary")],
        [button("📊 Statistika", callback_data="stats", style="primary")],
        [button("📢 Majburiy kanal/chat qo'shish", callback_data="add_required", style="success")],
        [button("📋 Majburiy obunalar", callback_data="required_list", style="primary")],
        [button("➖ Majburiy obunani o'chirish", callback_data="delete_required", style="danger")],
        [button("📨 Hammaga xabar yuborish", callback_data="broadcast", style="success")]
    ])


    
    return markup


def send_admin_panel(chat_id):
    bot.send_message(
        chat_id,
        "💎👨‍💻 Admin panel:\n\n"
        "Kerakli bo'limni tanlang:",
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
            "💎🔒 Botdan foydalanish uchun avval majburiy obunalarga qo'shiling!\n\n"
            "🔵 Kanalga obuna bo'ling\n"
            "🟢 Chatga qo'shiling\n"
            "🟣 Instagram sahifani kuzating\n\n"
            "✅ Keyin tekshirish tugmasini bosing.",
            reply_markup=subscribe_keyboard()
        )
        return

    bot.send_message(
        message.chat.id,
        "💎🎬 Xush kelibsiz!\n\n"
        "🔢 Kino kodini yuboring."
    )


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
            "✅ Obuna tasdiqlandi!\n\n🎬 Endi kino kodini yuboring."
        )
    else:
        bot.answer_callback_query(call.id, "❌ Hali obuna bo'lmagansiz!")
        bot.send_message(
            call.message.chat.id,
            "❌ Siz hali majburiy obunalarga qo'shilmagansiz.\n\n"
            "📢 Avval obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )

@bot.chat_join_request_handler()
def join_request(update):
    user = update.from_user
    chat = update.chat

    username = f"@{chat.username}" if chat.username else str(chat.id)

    join_requests.update_one(
        {
            "user_id": user.id,
            "username": username
        },
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
            "❌ Siz hali majburiy obunalarga qo'shilmagansiz.\n\n"
            "📢 Avval obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )


@bot.chat_join_request_handler()
def join_request(update):
    user = update.from_user
    chat = update.chat

    username = f"@{chat.username}" if chat.username else str(chat.id)

    join_requests.update_one(
        {
            "user_id": user.id,
            "username": username
        },
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



@bot.callback_query_handler(func=lambda call: call.data == "add_movie")
def add_movie(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)
    admin_states[call.from_user.id] = {"step": "waiting_code"}

    bot.send_message(
        call.message.chat.id,
        "🟢➕ Kino qo'shish boshlandi.\n\n"
        "🔢 Kino kodini yuboring. Masalan: 1"
    )


@bot.callback_query_handler(func=lambda call: call.data == "delete_movie")
def delete_movie(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)
    admin_states[call.from_user.id] = {"step": "delete_code"}

    bot.send_message(call.message.chat.id, "🔴🗑 O'chirmoqchi bo'lgan kino kodini yuboring:")


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

    text = "🔵🎬 Kinolar ro'yxati:\n\n"

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
        @bot.callback_query_handler(func=lambda call: call.data == "add_required")
def add_required(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)

    markup = keyboard([
        [button("📢 Oddiy kanal", callback_data="add_req_telegram", style="primary")],
        [button("💬 Public chat/guruh", callback_data="add_req_chat", style="success")],
        [button("📝 Zayafka kanal", callback_data="add_req_request", style="success")],
        [button("📸 Instagram", callback_data="add_req_instagram", style="primary")]
    ])

    bot.send_message(call.message.chat.id, "Qanday majburiy obuna qo'shasiz?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ["add_req_telegram", "add_req_chat", "add_req_request", "add_req_instagram"])
def add_required_type(call):
    if not is_admin(call.from_user.id):
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

    bot.send_message(call.message.chat.id, "📌 Nomini yuboring. Masalan: Kino kanal")


@bot.callback_query_handler(func=lambda call: call.data == "required_list")
def required_list(call):
    if not is_admin(call.from_user.id):
        return

    text = "📋 Majburiy obunalar:\n\n"

    for item in required_links.find().sort("_id", 1):
        text += f"🆔 ID: {item.get('link_id')}\n"
        text += f"📌 Nomi: {item.get('title')}\n"
        text += f"📎 Turi: {item.get('type')}\n"
        text += f"🔗 Link: {item.get('url')}\n\n"

    if text == "📋 Majburiy obunalar:\n\n":
        text = "📭 Hozircha majburiy obuna yo'q."

    bot.send_message(call.message.chat.id, text, reply_markup=admin_panel())


@bot.callback_query_handler(func=lambda call: call.data == "delete_required")
def delete_required(call):
    if not is_admin(call.from_user.id):
        return

    admin_states[call.from_user.id] = {"step": "delete_required"}
    bot.send_message(call.message.chat.id, "➖ O'chirmoqchi bo'lgan obuna ID sini yuboring.")


@bot.callback_query_handler(func=lambda call: call.data == "broadcast")
def broadcast(call):
    if not is_admin(call.from_user.id):
        return

    admin_states[call.from_user.id] = {"step": "broadcast"}
    bot.send_message(call.message.chat.id, "📨 Hammaga yuboriladigan xabarni yozing.")


    bot.answer_callback_query(call.id)

    users_count = users.count_documents({})
    movies_count = movies.count_documents({})
    links_count = links.count_documents({})

    bot.send_message(
        call.message.chat.id,
        "🟣📊 Bot statistikasi:\n\n"
        f"👥 Start bosgan odamlar: {users_count}\n"
        f"🎬 Kinolar soni: {movies_count}\n"
        f"📢 Majburiy obunalar: {links_count}",
        reply_markup=admin_panel()
    )


@bot.callback_query_handler(func=lambda call: call.data == "add_required")
def add_required(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🔵 Telegram kanal", callback_data="add_required_telegram"))
    markup.add(types.InlineKeyboardButton("🟢 Telegram chat/guruh", callback_data="add_required_chat"))
    markup.add(types.InlineKeyboardButton("🟣 Instagram", callback_data="add_required_instagram"))
    markup.add(types.InlineKeyboardButton("🟡 Boshqa link", callback_data="add_required_other"))

    bot.send_message(call.message.chat.id, "🟡📢 Qanday majburiy obuna qo'shasiz?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in [
    "add_required_telegram",
    "add_required_chat",
    "add_required_instagram",
    "add_required_other"
])
def add_required_type(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)

    type_map = {
        "add_required_telegram": "telegram",
        "add_required_chat": "chat",
        "add_required_instagram": "instagram",
        "add_required_other": "other"
    }

    admin_states[call.from_user.id] = {
        "step": "required_title",
        "type": type_map[call.data]
    }

    bot.send_message(
        call.message.chat.id,
        "📌 Obuna nomini yuboring.\n\n"
        "Masalan: Kino kanal"
    )


@bot.callback_query_handler(func=lambda call: call.data == "required_list")
def required_list(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)

    all_links = get_required_links()

    if not all_links:
        bot.send_message(call.message.chat.id, "📭 Majburiy obuna hali yo'q.", reply_markup=admin_panel())
        return

    text = "🟠📋 Majburiy obunalar ro'yxati:\n\n"

    for i, item in enumerate(all_links, start=1):
        text += f"{i}. 🆔 ID: {item.get('link_id')}\n"
        text += f"📌 Nomi: {item.get('title')}\n"
        text += f"📎 Turi: {item.get('type')}\n"
        text += f"🔗 Link: {item.get('url')}\n"
        text += f"👤 Username: {item.get('username', '-')}\n\n"

    bot.send_message(call.message.chat.id, text, reply_markup=admin_panel())


@bot.callback_query_handler(func=lambda call: call.data == "delete_required")
def delete_required(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!")
        return

    bot.answer_callback_query(call.id)
    admin_states[call.from_user.id] = {"step": "delete_required_id"}

    bot.send_message(
        call.message.chat.id,
        "🔴➖ O'chirmoqchi bo'lgan majburiy obuna ID sini yuboring.\n\n"
        "ID ni 🟠📋 Majburiy obunalar ro'yxati bo'limidan oling."
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
            "⚠️ Video qo'shish uchun avval 🟢➕ Kino qo'shish tugmasini bosing."
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
            step = state.get("step")

            if step == "waiting_code":
                if not text.isdigit():
                    bot.send_message(message.chat.id, "❌ Kod faqat raqam bo'lishi kerak. Masalan: 1")
                    return

                admin_states[user_id] = {
                    "step": "waiting_video",
                    "code": text
                }

                bot.send_message(message.chat.id, f"✅ Kod qabul qilindi: {text}\n\n🎥 Endi video yuboring:")
                return

            if step == "delete_code":
                result = movies.delete_one({"code": text})
                admin_states.pop(user_id, None)

                            if step == "required_title":
                admin_states[user_id]["title"] = text
                admin_states[user_id]["step"] = "required_username"

                if state.get("type") == "instagram":
                    bot.send_message(message.chat.id, "📸 Instagram link yuboring.")
                else:
                    bot.send_message(message.chat.id, "👤 Username yuboring. Masalan: @kanal_username")
                return

            if step == "required_username":
                link_type = state.get("type")
                title = state.get("title")
                link_id = uuid.uuid4().hex[:8]

                if link_type == "instagram":
                    url = text
                    username = ""
                else:
                    username = text if text.startswith("@") else "@" + text
                    url = f"https://t.me/{username.replace('@', '')}"

                required_links.insert_one({
                    "link_id": link_id,
                    "title": title,
                    "type": link_type,
                    "username": username,
                    "url": url
                })

                admin_states.pop(user_id, None)

                bot.send_message(
                    message.chat.id,
                    f"✅ Majburiy obuna qo'shildi!\n\n🆔 ID: {link_id}",
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


                if result.deleted_count:
                    bot.send_message(message.chat.id, f"✅ Kino o'chirildi!\n\n🔢 Kod: {text}", reply_markup=admin_panel())
                else:
                    bot.send_message(message.chat.id, "❌ Bunday kodli kino topilmadi.", reply_markup=admin_panel())
                return

            if step == "required_title":
                admin_states[user_id]["title"] = text
                admin_states[user_id]["step"] = "required_value"

                item_type = state.get("type")

                if item_type in ["telegram", "chat"]:
                    bot.send_message(
                        message.chat.id,
                        "👤 Username yuboring.\n\n"
                        "Masalan: @kanal_username yoki @chat_username"
                    )
                elif item_type == "instagram":
                    bot.send_message(
                        message.chat.id,
                        "🟣 Instagram link yuboring.\n\n"
                        "Masalan: https://instagram.com/username"
                    )
                else:
                    bot.send_message(
                        message.chat.id,
                        "🔗 Link yuboring.\n\n"
                        "Masalan: https://example.com"
                    )
                return

            if step == "required_value":
                item_type = state.get("type")
                title = state.get("title")
                link_id = uuid.uuid4().hex[:8]

                if item_type in ["telegram", "chat"]:
                    username = text.strip()

                    if not username.startswith("@"):
                        username = "@" + username

                    url = f"https://t.me/{username.replace('@', '')}"

                    links.insert_one({
                        "link_id": link_id,
                        "title": title,
                        "type": item_type,
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
                        f"📎 Turi: {item_type}\n"
                        f"👤 Username: {username}\n\n"
                        "⚠️ Bot kanal/chat ichida admin yoki a'zo bo'lishi kerak.",
                        reply_markup=admin_panel()
                    )
                    return

                url = text.strip()

                links.insert_one({
                    "link_id": link_id,
                    "title": title,
                    "type": item_type,
                    "username": "",
                    "url": url,
                    "required": True
                })

                admin_states.pop(user_id, None)

                bot.send_message(
                    message.chat.id,
                    "✅ Link qo'shildi!\n\n"
                    f"🆔 ID: {link_id}\n"
                    f"📌 Nomi: {title}\n"
                    f"🔗 Link: {url}\n\n"
                    "⚠️ Instagram va boshqa linklar avtomatik tekshirilmaydi, faqat tugma sifatida chiqadi.",
                    reply_markup=admin_panel()
                )
                return

            if step == "delete_required_id":
                result = links.delete_one({"link_id": text})
                admin_states.pop(user_id, None)

                if result.deleted_count:
                    bot.send_message(message.chat.id, "✅ Majburiy obuna o'chirildi!", reply_markup=admin_panel())
                else:
                    bot.send_message(message.chat.id, "❌ Bunday ID topilmadi.", reply_markup=admin_panel())
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
            "💎🔒 Botdan foydalanish uchun avval majburiy obunalarga qo'shiling!\n\n"
            "📢 Avval kanal/chatga qo'shiling.",
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
