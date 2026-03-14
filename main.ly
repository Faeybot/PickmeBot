import os
import telebot

TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

FEED_CHANNEL = "@pickmeindonesia"
DATING_CHANNEL = "@pickmedating"

user_state = {}

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Selamat datang di Pick Me Indonesia\n\n"
        "/feed - Posting ke Feed\n"
        "/dating - Posting Dating"
    )

@bot.message_handler(commands=['feed'])
def feed(message):
    user_state[message.chat.id] = "feed"
    bot.send_message(message.chat.id,"Kirim teks untuk Feed")

@bot.message_handler(commands=['dating'])
def dating(message):
    user_state[message.chat.id] = "dating"
    bot.send_message(message.chat.id,"Kirim profil dating")

@bot.message_handler(func=lambda message: True)
def handle(message):

    state = user_state.get(message.chat.id)

    if state == "feed":

        bot.send_message(
            FEED_CHANNEL,
            f"👤 POST FEED\n\n{message.text}\n\n#PickMeFeed"
        )

        bot.send_message(message.chat.id,"Posting berhasil")

        user_state.pop(message.chat.id)

    elif state == "dating":

        bot.send_message(
            DATING_CHANNEL,
            f"❤️ POST DATING\n\n{message.text}\n\n#PickMeDating"
        )

        bot.send_message(message.chat.id,"Profil dating berhasil")

        user_state.pop(message.chat.id)

bot.infinity_polling()
