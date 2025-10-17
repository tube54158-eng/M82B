# requirements:
# pip install python-telegram-bot requests

import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    Filters,
    CallbackContext,
)

# ---------------- CONFIG ----------------
TELEGRAM_BOT_TOKEN = "8014346088:AAFMaj9hV6t_rLKNlGsmZWtlRFcRtWAhg-k"  # সরাসরি কোডে
DEEPSEEK_API_KEY = "sk-72be0ce2ccac40a098bc7426cd2d55ba"  # সরাসরি কোডে
DEEPSEEK_ENDPOINT = "https://api.deepseek.ai/v1/chat"  # DeepSeek endpoint

chat_history = {}  # সংক্ষিপ্ত ইতিহাস (last 10 messages)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- AI REQUEST ----------------
def get_ai_reply(user_text: str, chat_id: int) -> str:
    payload = {"message": user_text}
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    try:
        resp = requests.post(DEEPSEEK_ENDPOINT, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("reply") or data.get("message") or str(data)
            return str(reply)
        else:
            logger.error("DeepSeek error %s: %s", resp.status_code, resp.text)
            return "দুঃখিত — সার্ভারের সমস্যা হয়েছে, পরে চেষ্টা করুন।"
    except requests.exceptions.RequestException:
        logger.exception("Request failed")
        return "দুঃখিত — AI সার্ভিসে যোগাযোগ করা যায়নি।"

# ---------------- BOT HANDLERS ----------------
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    display_name = user.first_name or user.username or "বন্ধু"
    keyboard = [[InlineKeyboardButton("Developer Info", callback_data="dev_info")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = (
        f"হ্যালো {display_name}! 👋\n\n"
        "আমি *Smart Bangla Ai* — আপনার সহায়ক চ্যাটবট।\n"
        "আমি ভালো কাজে সাহায্য করব; অবৈধ কাজে সাহায্য করব না।\n\n"
        "Developer Info জানতে নিচের বাটন চাপুন।"
    )
    update.message.reply_text(welcome_text, reply_markup=reply_markup)

def dev_info_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    dev_text = "© 2025  | Developed by Salman AI Ltd\nManaged by Salman Ahamed Robin"
    query.edit_message_text(dev_text)

def help_command(update: Update, context: CallbackContext):
    text = (
        "/start - শুরু\n"
        "/help - সাহায্য\n"
        "/about - বট সম্পর্কে\n"
        "সোজা কথা লিখে প্রশ্ন করুন — আমি উত্তর দেব।"
    )
    update.message.reply_text(text)

def about(update: Update, context: CallbackContext):
    update.message.reply_text("Smart Bangla Ai — আপনার বাংলা সহায়ক চ্যাটবট।")

def handle_message(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()
    lower = user_text.lower()
    illegal_keywords = ["বোমা", "হ্যাক", "চুরি", "অপরাধ", "হিংসা", "রাসায়নিক", "নকল"]
    if any(k in lower for k in illegal_keywords):
        update.message.reply_text(
            "দুঃখিত — আমি অবৈধ বা ক্ষতিকর কাজে সাহায্য করতে সক্ষম নই।"
        )
        return

    # সংক্ষিপ্ত ইতিহাস
    history = chat_history.setdefault(chat_id, [])
    history.append({"role": "user", "content": user_text})
    if len(history) > 10:
        history = history[-10:]
        chat_history[chat_id] = history

    reply = get_ai_reply(user_text, chat_id)
    history.append({"role": "bot", "content": reply})
    chat_history[chat_id] = history
    update.message.reply_text(reply)

def error_handler(update: Update, context: CallbackContext):
    logger.error("Exception while handling an update:", exc_info=context.error)

# ---------------- MAIN ----------------
def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("about", about))
    dp.add_handler(CallbackQueryHandler(dev_info_callback, pattern="^dev_info$"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_error_handler(error_handler)

    logger.info("Starting Smart Bangla Ai bot...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()