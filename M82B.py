#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import uuid
import shutil
import logging
from pathlib import Path
from datetime import datetime

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from yt_dlp import YoutubeDL

# ----------------- CONFIG -----------------
BOT_TOKEN = "8001674280:AAERnecjl4roU04UT4B2VkMLb3bQPKKgu4c"
TMP_DIR = Path("./tmp_dl")
TMP_DIR.mkdir(exist_ok=True, parents=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ----------------- HARDCODED NETSCAPE COOKIES -----------------
# Netscape HTTP Cookie File Format
COOKIES_NETSCAPE = """
# Netscape HTTP Cookie File
# This file is generated for Doob Ai Bot
.youtube.com    TRUE    /   FALSE   0   SID     XXXXXXXXXXXXXXXXXXXXXXXX
.youtube.com    TRUE    /   FALSE   0   HSID    XXXXXXXXXXXXXXXXXXXXXXXX
.youtube.com    TRUE    /   FALSE   0   SSID    XXXXXXXXXXXXXXXXXXXXXXXX
"""

def write_cookie_file():
    cookie_path = TMP_DIR / "cookies_runtime.txt"
    cookie_path.write_text(COOKIES_NETSCAPE.strip())
    cookie_path.chmod(0o600)
    return str(cookie_path)

# ----------------- HELPERS -----------------
def gen_temp_name(prefix="dl"):
    return f"{prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

def clean_files(*paths):
    for p in paths:
        try:
            p = Path(p)
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove {p}: {e}")

# ----------------- YT-DLP FUNCTIONS -----------------
def ytdlp_download_best(url: str, out_template: str):
    opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "continuedl": True,
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
        "cookiefile": write_cookie_file()
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        fn = ydl.prepare_filename(info)
        base = fn.rsplit(".",1)[0]
        mp4_file = base + ".mp4"
        if os.path.exists(mp4_file):
            return mp4_file, info
        if os.path.exists(fn):
            return fn, info
    raise FileNotFoundError("Downloaded file not found after yt-dlp run.")

def ytdlp_download_audio_mp3(url: str, out_template: str):
    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "continuedl": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
        "cookiefile": write_cookie_file()
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        fn = ydl.prepare_filename(info)
        base = fn.rsplit(".",1)[0]
        mp3_file = base + ".mp3"
        if os.path.exists(mp3_file):
            return mp3_file, info
    raise FileNotFoundError("Audio file not found after yt-dlp run.")

# ----------------- TELEGRAM HANDLERS -----------------
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    user_name = message.from_user.first_name or "বন্ধু"
    txt = (
        f"👋 হ্যালো {user_name}!\n\n"
        "আমি 🤖 **Doob Ai**, আপনার ভিডিও ও অডিও ডাউনলোড সহকারী।\n\n"
        "🎥 শুধু ইউটিউব, টিকটক, ফেসবুক বা ইনস্টাগ্রামের লিংক পাঠান — "
        "তারপর আমি ভিডিও বা অডিও হিসেবে ডাউনলোডের অপশন দেবো।\n\n"
        "↓"
        
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Developer Info", callback_data="dev_info"))
    bot.reply_to(message, txt, reply_markup=markup)

@bot.message_handler(func=lambda m: True, content_types=['text'])
def catch_all(message):
    tokens = message.text.strip().split()
    url_candidate = next((t for t in tokens if "youtube.com" in t or "youtu.be" in t or
                          "tiktok.com" in t or "instagram.com" in t or "facebook.com" in t), None)
    if not url_candidate:
        bot.reply_to(message, "❌ দুঃখিত, আমি কোনো বৈধ URL চিহ্নিত করতে পারিনি।")
        return

    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("🎥 Video (MP4)", callback_data=f"video|{url_candidate}"),
        InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"audio|{url_candidate}")
    )
    bot.send_message(message.chat.id, "নিচের বোতামে ক্লিক করে ভিডিও বা অডিও হিসেবে ডাউনলোড করুন:", reply_markup=markup)

# ----------------- CALLBACK HANDLER -----------------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: CallbackQuery):
    try:
        data = call.data
        if data == "dev_info":
            bot.send_message(call.message.chat.id,
                "Developer: Salman Ai Ltd\nManaged by: Salman Ahamed Robin")
            return

        mode, url = data.split("|", 1)
        bot.edit_message_text("ডাউনলোড শুরু হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...", call.message.chat.id, call.message.message_id)
        unique = gen_temp_name("dl")
        out_template = str(TMP_DIR / (unique + ".%(ext)s"))

        if mode == "audio":
            result_path, info = ytdlp_download_audio_mp3(url, out_template)
            with open(result_path, "rb") as f:
                bot.send_document(call.message.chat.id, f, caption=f"{info.get('title','')} (MP3)")
        else:
            result_path, info = ytdlp_download_best(url, out_template)
            filesize = result_path.stat().st_size
            with open(result_path, "rb") as f:
                if filesize <= 50*1024*1024:
                    bot.send_video(call.message.chat.id, f, caption=info.get('title',''))
                else:
                    bot.send_document(call.message.chat.id, f, caption=info.get('title',''))

        bot.send_message(call.message.chat.id, "✅ ডাউনলোড সম্পন্ন হয়েছে!")
    except Exception as e:
        logger.exception("Error during download/upload")
        bot.send_message(call.message.chat.id, f"⚠️ একটি ত্রুটি ঘটেছে: {str(e)}")
    finally:
        for p in TMP_DIR.glob(f"{unique}*"):
            try:
                if p.is_file():
                    p.unlink()
                elif p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
            except:
                pass

# ----------------- RUN -----------------
if __name__ == "__main__":
    print("Doob Ai Bot is running with Inline Buttons...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("Bot stopped manually.")
    except Exception as e:
        logger.exception("Bot stopped unexpectedly: %s", e)