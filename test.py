import os
import time
import json
import threading
from datetime import datetime, timezone

import certifi
from bson import ObjectId
from flask import Flask
import telebot
from pymongo import MongoClient


TOKEN = os.getenv("8936595051:AAHhoyn2O3bd9IRsqogmA61Olky9EGCKE-M", "8936595051:AAHhoyn2O3bd9IRsqogmA61Olky9EGCKE-M")
ADMIN_ID = int(os.getenv("6968399046", os.getenv("6968399046", "0").split(",")[0] or "0"))
MONGO_URL = os.getenv("MONGODB_URI", "mongodb+srv://tojiyevjavohir67_db_user:jtwASN46W0zU9sw7@cluster0.pysrg0q.mongodb.net/?appName=Cluster0")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@java_free_things_bot")

REFERRAL_PRICE = 1
MIN_WITHDRAW = 15

# Premium emoji ID larni shu yerga qo'yasiz. Bilmasangiz bo'sh qoldiring: "".
PREMIUM_EMOJI_IDS = {
    "star": os.getenv("STAR_EMOJI_ID", ""),
    "add": "5030787243543888610",
    "delete": "5271851165024271824",
    "list": "5233585291339536488",
    "stats": "5233308575186591026",
    "channel": "5195028614009103813",
    "check": "5195424863396862786",
    "broadcast": "5461054558996282111",
    "money": "5233672483470612683",
    "ref": "5233585291339536488",
}


bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
client = MongoClient(
    MONGO_URL,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=20000,
)
db = client["referal_stars_bot"]

users = db["users"]
required_links = db["required_links"]
withdrawals = db["withdrawals"]

states = {}
app = Flask(__name__)


def now():
    return datetime.now(timezone.utc)


def star_icon():
    emoji_id = PREMIUM_EMOJI_IDS.get("star", "")
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">⭐</tg-emoji>'
    return "⭐"


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


def get_bot_username():
    if BOT_USERNAME:
        return BOT_USERNAME.replace("@", "")
    return bot.get_me().username


def referral_link(user_id):
    return f"https://t.me/{get_bot_username()}?start=ref_{user_id}"


def save_user(message, referred_by=None):
    user = message.from_user
    if not user:
        return None

    set_on_insert = {
        "user_id": user.id,
        "balance": 0,
        "earned_total": 0,
        "withdrawn_total": 0,
        "referrals_count": 0,
        "referral_rewarded": False,
        "created_at": now(),
    }
    if referred_by and referred_by != user.id:
        set_on_insert["referred_by"] = referred_by

    return users.find_one_and_update(
        {"user_id": user.id},
        {
            "$set": {
                "user_id": user.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username or "",
                "updated_at": now(),
            },
            "$setOnInsert": set_on_insert,
        },
        upsert=True,
        return_document=True,
    )


def user_name(user_doc):
    return user_doc.get("first_name") or user_doc.get("username") or str(user_doc.get("user_id"))


def check_subscription(user_id):
    if is_admin(user_id):
        return True

    for item in required_links.find({"active": {"$ne": False}}):
        username = item.get("username", "")
        link_type = item.get("type", "telegram")

        if link_type == "instagram":
            continue

        try:
            member = bot.get_chat_member(username, user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            print("OBUNA TEKSHIRISH XATOSI:", e)
            return False

    return True


def reward_referrer(user_id):
    user = users.find_one({"user_id": user_id}) or {}
    referrer_id = user.get("referred_by")

    if not referrer_id or user.get("referral_rewarded"):
        return
    if not check_subscription(user_id):
        return

    changed = users.update_one(
        {"user_id": user_id, "referral_rewarded": {"$ne": True}},
        {"$set": {"referral_rewarded": True, "rewarded_at": now()}},
    )
    if changed.modified_count != 1:
        return

    users.update_one(
        {"user_id": referrer_id},
        {
            "$inc": {
                "balance": REFERRAL_PRICE,
                "earned_total": REFERRAL_PRICE,
                "referrals_count": 1,
            },
            "$set": {"updated_at": now()},
        },
    )

    try:
        bot.send_message(
            referrer_id,
            f"{star_icon()} <b>Yangi referal!</b>\n\nBalansingizga <b>{REFERRAL_PRICE} Stars</b> qo'shildi.",
        )
    except Exception:
        pass


def subscribe_keyboard():
    rows = []
    for item in required_links.find({"active": {"$ne": False}}).sort("_id", 1):
        rows.append([
            make_button(
                f"📌 Qo'shilish: {item.get('title', 'Kanal')}",
                url=item.get("url", ""),
                style="primary",
                emoji_key="channel",
            )
        ])
    rows.append([make_button("✅ Tekshirish", callback_data="check_sub", style="success", emoji_key="check")])
    return make_keyboard(rows)


def user_panel():
    return make_keyboard([
        [
            make_button("⭐ Balans", callback_data="balance", style="primary", emoji_key="star"),
            make_button("🔗 Referal link", callback_data="ref_link", style="success", emoji_key="ref"),
        ],
        [
            make_button("💸 Stars yechish", callback_data="withdraw", style="success", emoji_key="money"),
            make_button("📊 Statistika", callback_data="my_stats", style="primary", emoji_key="stats"),
        ],
        [make_button("✅ Obunani tekshirish", callback_data="check_sub", style="primary", emoji_key="check")],
    ])


def admin_panel():
    return make_keyboard([
        [make_button("📊 Statistika", callback_data="admin_stats", style="primary", emoji_key="stats")],
        [make_button("💸 Yechish so'rovlari", callback_data="withdraw_list", style="success", emoji_key="money")],
        [make_button("📈 Yechilgan statistika", callback_data="withdraw_stats", style="primary", emoji_key="stats")],
        [make_button("📌 Majburiy obuna qo'shish", callback_data="add_required", style="success", emoji_key="channel")],
        [make_button("📋 Majburiy obunalar", callback_data="required_list", style="primary", emoji_key="list")],
        [make_button("🗑 Majburiy obunani o'chirish", callback_data="delete_required", style="danger", emoji_key="delete")],
        [make_button("📨 Hammaga xabar yuborish", callback_data="broadcast", style="success", emoji_key="broadcast")],
    ])


def withdraw_admin_keyboard(withdraw_id):
    return make_keyboard([
        [
            make_button("✅ To'landi", callback_data=f"approve_withdraw:{withdraw_id}", style="success", emoji_key="check"),
            make_button("❌ Rad etish", callback_data=f"reject_withdraw:{withdraw_id}", style="danger", emoji_key="delete"),
        ]
    ])


def send_user_panel(chat_id, user_doc):
    bot.send_message(
        chat_id,
        f"👋 <b>Hush kelibsiz, {user_name(user_doc)}!</b>\n\n"
        f"{star_icon()} Referal narxi: <b>{REFERRAL_PRICE} Stars</b>\n"
        f"💸 Minimum yechish: <b>{MIN_WITHDRAW} Stars</b>\n\n"
        "Quyidagi foydalanuvchi panelidan foydalaning.",
        reply_markup=user_panel(),
        disable_web_page_preview=True,
    )


def send_admin_panel(chat_id):
    bot.send_message(chat_id, "💎👨‍💻 <b>Admin panel</b>\n\nKerakli bo'limni tanlang:", reply_markup=admin_panel())


def normalize_channel(text):
    value = text.strip()
    if value.startswith("https://t.me/"):
        username = value.replace("https://t.me/", "").split("/", 1)[0]
        return f"@{username}", f"https://t.me/{username}"
    if value.startswith("t.me/"):
        username = value.replace("t.me/", "").split("/", 1)[0]
        return f"@{username}", f"https://t.me/{username}"
    if value.startswith("@"):
        return value, f"https://t.me/{value[1:]}"
    return "@" + value, f"https://t.me/{value}"


@bot.message_handler(commands=["start"])
def start(message):
    print("START BOSILDI:", message.from_user.id)

    referred_by = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("ref_"):
        try:
            referred_by = int(parts[1].replace("ref_", ""))
        except ValueError:
            referred_by = None

    user_doc = save_user(message, referred_by)
    user_id = message.from_user.id

    if is_admin(user_id):
        send_admin_panel(message.chat.id)
        return

    if not check_subscription(user_id):
        bot.send_message(
            message.chat.id,
            "💎🔒 Botdan foydalanish uchun avval majburiy obunalarga qo'shiling!\n\n"
            "✅ Keyin tekshirish tugmasini bosing.",
            reply_markup=subscribe_keyboard(),
        )
        return

    reward_referrer(user_id)
    send_user_panel(message.chat.id, user_doc)


@bot.message_handler(commands=["admin", "panel"])
def admin_command(message):
    if is_admin(message.from_user.id):
        send_admin_panel(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub(call):
    if check_subscription(call.from_user.id):
        reward_referrer(call.from_user.id)
        user_doc = users.find_one({"user_id": call.from_user.id}) or {}
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
        send_user_panel(call.message.chat.id, user_doc)
    else:
        bot.answer_callback_query(call.id, "❌ Hali obuna bo'lmagansiz!", show_alert=True)
        bot.send_message(call.message.chat.id, "📢 Avval majburiy obunalarga qo'shiling.", reply_markup=subscribe_keyboard())


@bot.callback_query_handler(func=lambda call: call.data in ["balance", "ref_link", "withdraw", "my_stats"])
def user_callbacks(call):
    user_doc = users.find_one({"user_id": call.from_user.id}) or save_user(call.message)

    if not check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "Avval obuna bo'ling.", show_alert=True)
        bot.send_message(call.message.chat.id, "📢 Avval majburiy obunalarga qo'shiling.", reply_markup=subscribe_keyboard())
        return

    if call.data == "balance":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"{star_icon()} <b>Balans</b>\n\n"
            f"Joriy balans: <b>{user_doc.get('balance', 0)} Stars</b>\n"
            f"Jami ishlangan: <b>{user_doc.get('earned_total', 0)} Stars</b>\n"
            f"Jami yechilgan: <b>{user_doc.get('withdrawn_total', 0)} Stars</b>",
            reply_markup=user_panel(),
        )

    if call.data == "ref_link":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🔗 <b>Sizning referal linkingiz</b>\n\n"
            f"<code>{referral_link(call.from_user.id)}</code>\n\n"
            f"Har bir taklif qilingan do'stingiz uchun <b>{REFERRAL_PRICE} Stars</b> olasiz.",
            reply_markup=user_panel(),
            disable_web_page_preview=True,
        )

    if call.data == "my_stats":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "📊 <b>Mening statistikam</b>\n\n"
            f"👥 Referallar: <b>{user_doc.get('referrals_count', 0)}</b>\n"
            f"{star_icon()} Balans: <b>{user_doc.get('balance', 0)} Stars</b>\n"
            f"💸 Yechilgan: <b>{user_doc.get('withdrawn_total', 0)} Stars</b>",
            reply_markup=user_panel(),
        )

    if call.data == "withdraw":
        balance = int(user_doc.get("balance", 0))
        if balance < MIN_WITHDRAW:
            bot.answer_callback_query(call.id, f"Minimum yechish {MIN_WITHDRAW} Stars.", show_alert=True)
            return
        states[call.from_user.id] = {"step": "withdraw_amount"}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"💸 Yechmoqchi bo'lgan Stars miqdorini yuboring.\n\nBalans: <b>{balance}</b>")


@bot.callback_query_handler(func=lambda call: call.data in [
    "admin_stats",
    "withdraw_list",
    "withdraw_stats",
    "add_required",
    "required_list",
    "delete_required",
    "broadcast",
])
def admin_callbacks(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    if call.data == "admin_stats":
        refs = sum(u.get("referrals_count", 0) for u in users.find({}, {"referrals_count": 1}))
        earned = sum(u.get("earned_total", 0) for u in users.find({}, {"earned_total": 1}))
        bot.send_message(
            call.message.chat.id,
            "📊 <b>Bot statistikasi</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{users.count_documents({})}</b>\n"
            f"🔗 Referallar: <b>{refs}</b>\n"
            f"{star_icon()} Jami ishlangan: <b>{earned} Stars</b>\n"
            f"📢 Majburiy obunalar: <b>{required_links.count_documents({'active': {'$ne': False}})}</b>",
            reply_markup=admin_panel(),
        )

    if call.data == "withdraw_stats":
        paid = list(withdrawals.find({"status": "approved"}))
        total_paid = sum(int(x.get("amount", 0)) for x in paid)
        pending = withdrawals.count_documents({"status": "pending"})
        bot.send_message(
            call.message.chat.id,
            "📈 <b>Yechilgan Stars statistikasi</b>\n\n"
            f"✅ To'langan so'rovlar: <b>{len(paid)}</b>\n"
            f"⏳ Kutilayotgan so'rovlar: <b>{pending}</b>\n"
            f"💸 Jami yechilgan: <b>{total_paid} Stars</b>",
            reply_markup=admin_panel(),
        )

    if call.data == "withdraw_list":
        pending = list(withdrawals.find({"status": "pending"}).sort("_id", 1).limit(10))
        if not pending:
            bot.send_message(call.message.chat.id, "📭 Kutilayotgan yechish so'rovlari yo'q.", reply_markup=admin_panel())
            return
        for item in pending:
            user_doc = users.find_one({"user_id": item["user_id"]}) or {}
            bot.send_message(
                call.message.chat.id,
                "💸 <b>Yechish so'rovi</b>\n\n"
                f"👤 User: <code>{item['user_id']}</code> @{user_doc.get('username', '-')}\n"
                f"{star_icon()} Miqdor: <b>{item['amount']} Stars</b>\n"
                f"📝 Ma'lumot: <code>{item.get('payout_info', '-')}</code>",
                reply_markup=withdraw_admin_keyboard(item["_id"]),
            )

    if call.data == "add_required":
        states[call.from_user.id] = {"step": "required_title"}
        bot.send_message(call.message.chat.id, "📌 Majburiy obuna nomini yuboring. Masalan: Kino kanal")

    if call.data == "required_list":
        items = list(required_links.find({"active": {"$ne": False}}).sort("_id", 1))
        if not items:
            bot.send_message(call.message.chat.id, "📭 Majburiy obuna yo'q.", reply_markup=admin_panel())
            return
        text = "📋 <b>Majburiy obunalar</b>\n\n"
        for item in items:
            text += f"🆔 ID: <code>{item.get('link_id')}</code>\n"
            text += f"📌 Nomi: {item.get('title')}\n"
            text += f"👤 Username: {item.get('username')}\n"
            text += f"🔗 Link: {item.get('url')}\n\n"
        bot.send_message(call.message.chat.id, text[:4000], reply_markup=admin_panel())

    if call.data == "delete_required":
        states[call.from_user.id] = {"step": "delete_required"}
        bot.send_message(call.message.chat.id, "🗑 O'chirmoqchi bo'lgan majburiy obuna ID sini yuboring.")

    if call.data == "broadcast":
        states[call.from_user.id] = {"step": "broadcast"}
        bot.send_message(call.message.chat.id, "📨 Hammaga yuboriladigan xabarni yuboring:")


@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_withdraw:") or call.data.startswith("reject_withdraw:"))
def withdraw_action(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz!", show_alert=True)
        return

    action, withdraw_id = call.data.split(":", 1)
    try:
        oid = ObjectId(withdraw_id)
    except Exception:
        bot.answer_callback_query(call.id, "ID xato.", show_alert=True)
        return

    item = withdrawals.find_one({"_id": oid, "status": "pending"})
    if not item:
        bot.answer_callback_query(call.id, "So'rov topilmadi yoki yopilgan.", show_alert=True)
        return

    if action == "approve_withdraw":
        withdrawals.update_one({"_id": oid}, {"$set": {"status": "approved", "admin_id": call.from_user.id, "approved_at": now()}})
        users.update_one({"user_id": item["user_id"]}, {"$inc": {"withdrawn_total": int(item["amount"])}})
        bot.answer_callback_query(call.id, "✅ To'landi.")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(item["user_id"], f"✅ <b>{item['amount']} Stars</b> yechish so'rovingiz to'landi.")

    if action == "reject_withdraw":
        withdrawals.update_one({"_id": oid}, {"$set": {"status": "rejected", "admin_id": call.from_user.id, "rejected_at": now()}})
        users.update_one({"user_id": item["user_id"]}, {"$inc": {"balance": int(item["amount"])}})
        bot.answer_callback_query(call.id, "❌ Rad etildi.")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(item["user_id"], f"❌ So'rov rad etildi. <b>{item['amount']} Stars</b> balansga qaytarildi.")


@bot.message_handler(content_types=["text", "photo", "video", "document", "animation", "sticker"])
def handle_message(message):
    save_user(message)
    user_id = message.from_user.id
    text = (message.text or "").strip()
    state = states.get(user_id)

    if state and state.get("step") == "withdraw_amount":
        if not text.isdigit():
            bot.send_message(message.chat.id, "❌ Miqdor faqat raqam bo'lishi kerak.")
            return
        amount = int(text)
        user_doc = users.find_one({"user_id": user_id}) or {}
        balance = int(user_doc.get("balance", 0))
        if amount < MIN_WITHDRAW:
            bot.send_message(message.chat.id, f"❌ Minimum yechish {MIN_WITHDRAW} Stars.")
            return
        if amount > balance:
            bot.send_message(message.chat.id, f"❌ Balansingizda faqat {balance} Stars bor.")
            return
        states[user_id] = {"step": "withdraw_info", "amount": amount}
        bot.send_message(message.chat.id, "📝 Stars qabul qilish uchun username yoki izoh yuboring.")
        return

    if state and state.get("step") == "withdraw_info":
        amount = int(state["amount"])
        changed = users.update_one({"user_id": user_id, "balance": {"$gte": amount}}, {"$inc": {"balance": -amount}})
        if changed.modified_count != 1:
            states.pop(user_id, None)
            bot.send_message(message.chat.id, "❌ Balans yetarli emas.", reply_markup=user_panel())
            return
        inserted = withdrawals.insert_one({
            "user_id": user_id,
            "amount": amount,
            "payout_info": text,
            "status": "pending",
            "created_at": now(),
        })
        states.pop(user_id, None)
        bot.send_message(message.chat.id, "✅ Yechish so'rovingiz adminga yuborildi.", reply_markup=user_panel())
        try:
            bot.send_message(
                ADMIN_ID,
                "💸 <b>Yangi yechish so'rovi</b>\n\n"
                f"👤 User: <code>{user_id}</code> @{message.from_user.username or '-'}\n"
                f"{star_icon()} Miqdor: <b>{amount} Stars</b>\n"
                f"📝 Ma'lumot: <code>{text}</code>",
                reply_markup=withdraw_admin_keyboard(inserted.inserted_id),
            )
        except Exception:
            pass
        return

    if is_admin(user_id) and state:
        step = state.get("step")

        if step == "required_title":
            states[user_id] = {"step": "required_value", "title": text}
            bot.send_message(message.chat.id, "👤 Kanal username/link yuboring. Masalan: @kanal")
            return

        if step == "required_value":
            username, url = normalize_channel(text)
            link_id = str(ObjectId())[-8:]
            required_links.insert_one({
                "link_id": link_id,
                "title": state.get("title"),
                "type": "telegram",
                "username": username,
                "url": url,
                "active": True,
                "created_at": now(),
            })
            states.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                "✅ Majburiy obuna qo'shildi!\n\n"
                f"🆔 ID: <code>{link_id}</code>\n"
                f"📌 Nomi: {state.get('title')}\n"
                f"👤 Username: {username}\n"
                f"🔗 Link: {url}",
                reply_markup=admin_panel(),
            )
            return

        if step == "delete_required":
            result = required_links.update_one({"link_id": text}, {"$set": {"active": False}})
            states.pop(user_id, None)
            if result.matched_count:
                bot.send_message(message.chat.id, "✅ Majburiy obuna o'chirildi.", reply_markup=admin_panel())
            else:
                bot.send_message(message.chat.id, "❌ Bunday ID topilmadi.", reply_markup=admin_panel())
            return

        if step == "broadcast":
            states.pop(user_id, None)
            success = 0
            failed = 0
            for user in users.find():
                try:
                    bot.copy_message(user["user_id"], message.chat.id, message.message_id)
                    success += 1
                    time.sleep(0.05)
                except Exception:
                    failed += 1
            bot.send_message(message.chat.id, f"📨 Xabar yuborildi!\n\n✅ Yetib bordi: {success}\n❌ Xato: {failed}", reply_markup=admin_panel())
            return

    if is_admin(user_id):
        send_admin_panel(message.chat.id)
        return

    if not check_subscription(user_id):
        bot.send_message(message.chat.id, "💎🔒 Botdan foydalanish uchun avval majburiy obunalarga qo'shiling!", reply_markup=subscribe_keyboard())
        return

    user_doc = users.find_one({"user_id": user_id}) or {}
    send_user_panel(message.chat.id, user_doc)


@app.route("/", methods=["GET"])
def home():
    return "✅ Referal Stars bot ishlayapti", 200


def ensure_indexes():
    users.create_index("user_id", unique=True)
    required_links.create_index("link_id")
    withdrawals.create_index("status")


def run_bot():
    print("✅ Referal Stars bot ishga tushmoqda...")
    try:
        ensure_indexes()
    except Exception as e:
        print("⚠️ Index yaratish xatosi:", e)

    while True:
        try:
            bot.remove_webhook()
            print("✅ Webhook o'chirildi")
            bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
        except Exception as e:
            print("❌ Bot polling xatosi:", e)
            print("🔁 Bot 5 soniyadan keyin qayta ishga tushadi...")
            time.sleep(5)


if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=False)
