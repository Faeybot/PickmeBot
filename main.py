import os
import telebot
from telebot import types
import time

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# ===== CHANNEL & GROUP =====
FEED_CHANNEL = "@pickmeindonesia"
DATING_CHANNEL = "@pickmedating"
FEED_GROUP = "@pickmechat"
DATING_GROUP = "@pickmelounge"

# ===== LOCATION =====
LOCATIONS = {
    "Sumatera": ["Sumatera"],
    "Kalimantan": ["Kalimantan"],
    "Sulawesi": ["Sulawesi"],
    "Jawa Barat": ["Jawa Barat", "Banten", "DKI Jakarta"],
    "Jawa Tengah": ["Jawa Tengah", "Yogyakarta"],
    "Jawa Timur": ["Jawa Timur"],
    "Bali": ["Bali", "Nusa Tenggara"]
}

# ===== USER STATE =====
user_state = {}          # user_id -> "feed"/"dating"/"comment"
last_post_time = {}      # anti spam
post_messages = {}       # message_id -> {type, original_user, likes, comments, timestamp}

# ===== ADMIN =====
ADMINS = [123456789]     # ganti dengan user_id admin Telegram

# ===== HELPERS =====
def can_post(user_id):
    now = time.time()
    if user_id in last_post_time and now - last_post_time[user_id] < 300:
        return False
    last_post_time[user_id] = now
    return True

def check_location(user_location):
    for key, vals in LOCATIONS.items():
        if user_location in vals:
            return key
    return None

def is_joined(user_id, channel):
    try:
        member = bot.get_chat_member(channel, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def forward_comment_to_group(post_id, user_id, comment_text):
    post = post_messages.get(post_id)
    if not post:
        return
    group = FEED_GROUP if post["type"]=="feed" else DATING_GROUP
    bot.send_message(group, f"💬 Comment dari {user_id}:\n{comment_text}")

def build_keyboard(post_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("❤️ Like", callback_data=f"like_{post_id}"),
        types.InlineKeyboardButton("💬 Comment", callback_data=f"comment_{post_id}"),
        types.InlineKeyboardButton("➡️ Next", callback_data=f"next_{post_id}")
    )
    return keyboard

# ===== COMMANDS =====
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Selamat datang di Pick Me Indonesia (Production Ready)!\n\n"
        "/feed - Posting Feed\n"
        "/dating - Posting Dating\n"
        "/stats - Lihat statistik user/admin"
    )

@bot.message_handler(commands=['feed'])
def feed(message):
    if not is_joined(message.chat.id, FEED_CHANNEL):
        bot.send_message(message.chat.id, f"⚠️ Kamu harus join {FEED_CHANNEL} dulu!")
        return
    user_state[message.chat.id] = "feed"
    bot.send_message(message.chat.id, "📌 Kirim teks/foto untuk Feed")

@bot.message_handler(commands=['dating'])
def dating(message):
    if not is_joined(message.chat.id, DATING_CHANNEL):
        bot.send_message(message.chat.id, f"⚠️ Kamu harus join {DATING_CHANNEL} dulu!")
        return
    user_state[message.chat.id] = "dating"
    bot.send_message(message.chat.id, "❤️ Kirim profil dating (nama, umur, lokasi)")

@bot.message_handler(commands=['stats'])
def stats(message):
    user_id = message.chat.id
    if user_id not in ADMINS:
        bot.send_message(user_id, "⚠️ Hanya admin yang bisa melihat statistik.")
        return
    msg = "📊 Statistik Postingan:\n"
    for pid, data in post_messages.items():
        msg += f"PostID {pid}: {len(data['likes'])} Likes, {len(data['comments'])} Comments\n"
    bot.send_message(user_id, msg)

# ===== HANDLE POSTS =====
@bot.message_handler(content_types=['text', 'photo'])
def handle_post(message):
    state = user_state.get(message.chat.id)
    user_id = message.chat.id

    if state is None:
        return

    if not can_post(user_id):
        bot.send_message(user_id, "⚠️ Tunggu 5 menit sebelum posting lagi.")
        return

    # determine channel
    channel = FEED_CHANNEL if state=="feed" else DATING_CHANNEL

    # handle location for dating
    if state=="dating" and message.content_type=="text":
        lines = message.text.splitlines()
        loc_line = next((l for l in lines if "lokasi" in l.lower()), "")
        user_location = loc_line.split(":")[-1].strip() if loc_line else ""
        if check_location(user_location) is None:
            bot.send_message(user_id, "⚠️ Lokasi tidak valid atau belum tersedia.")
            return

    # send message with inline keyboard
    keyboard = build_keyboard(int(time.time()))
    try:
        if message.content_type == "photo":
            sent = bot.send_photo(channel, message.photo[-1].file_id,
                                  caption=message.caption or "", reply_markup=keyboard)
        else:
            sent = bot.send_message(channel, message.text, reply_markup=keyboard)
        # register post
        post_messages[sent.message_id] = {
            "type": state,
            "user": user_id,
            "likes": [],
            "comments": [],
            "timestamp": time.time()
        }
        bot.send_message(user_id, "✅ Post berhasil dikirim!")
    except Exception as e:
        bot.send_message(user_id, f"❌ Gagal post: {e}")
    user_state.pop(user_id)

# ===== CALLBACK HANDLER =====
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data
    user_id = call.from_user.id
    if "_" not in data:
        return
    action, post_id = data.split("_")
    post_id = int(post_id)
    post = post_messages.get(post_id)
    if not post:
        bot.answer_callback_query(call.id, "Post tidak tersedia")
        return
    group = FEED_GROUP if post["type"]=="feed" else DATING_GROUP

    if action=="like":
        if user_id not in post["likes"]:
            post["likes"].append(user_id)
            bot.answer_callback_query(call.id, "❤️ Like tercatat!")
            bot.send_message(group, f"❤️ User {user_id} menyukai post ini!")
        else:
            bot.answer_callback_query(call.id, "⚠️ Kamu sudah like sebelumnya.")

    elif action=="comment":
        user_state[user_id] = f"comment_{post_id}"
        bot.answer_callback_query(call.id, "💬 Silakan kirim komentar kamu.")

    elif action=="next":
        bot.answer_callback_query(call.id, "➡️ Swipe ke post berikutnya!")

# ===== HANDLE COMMENTS =====
@bot.message_handler(func=lambda m: user_state.get(m.chat.id,"").startswith("comment_"))
def handle_comment(message):
    user_id = message.chat.id
    state = user_state[user_id]
    post_id = int(state.split("_")[1])
    post = post_messages.get(post_id)
    if post:
        post["comments"].append((user_id, message.text))
        group = FEED_GROUP if post["type"]=="feed
