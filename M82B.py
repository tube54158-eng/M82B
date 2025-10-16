#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import uuid
import shutil
import logging
import subprocess
from pathlib import Path
from datetime import datetime

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from yt_dlp import YoutubeDL

# ----------------- CONFIG -----------------
BOT_TOKEN = "8001674280:AAGXLbzL-d2GGbIo-V_lwS4JTjlMn-0x2nM"
TMP_DIR = Path("./tmp_dl")
TMP_DIR.mkdir(exist_ok=True, parents=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL_REGEX = re.compile(r'^(https?://)?([A-Za-z0-9-]+\.)+[A-Za-z]{2,}(/\S*)?$')

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ----------------- HELPERS -----------------
def is_likely_url(text: str) -> bool:
    if not text:
        return False
    text = text.strip()
    if text.startswith(("http://", "https://", "www.")):
        return True
    if URL_REGEX.search(text):
        return True
    keywords = [
        "youtube.com", "youtu.be", "tiktok.com", "instagram.com",
        "facebook.com", "x.com", "twitter.com", "vm.tiktok.com"
    ]
    return any(k in text.lower() for k in keywords)

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
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fn = ydl.prepare_filename(info)
            base = os.path.splitext(fn)[0]
            mp4_file = base + ".mp4"
            if os.path.exists(mp4_file):
                return mp4_file, info
            if os.path.exists(fn):
                return fn, info
            for ext in [".mp4", ".mkv", ".webm"]:
                cand = base + ext
                if os.path.exists(cand):
                    return cand, info
    except Exception as e:
        raise RuntimeError("এই ভিডিওটি ডাউনলোড করা যাবে না বা সুরক্ষিত।") from e
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
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fn = ydl.prepare_filename(info)
            base = os.path.splitext(fn)[0]
            mp3_file = base + ".mp3"
            if os.path.exists(mp3_file):
                return mp3_file, info
            for ext in [".m4a", ".webm", ".opus"]:
                cand = base + ext
                if os.path.exists(cand):
                    conv = base + ".mp3"
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", str(cand), "-vn", "-ab", "192k", str(conv)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    if os.path.exists(conv):
                        return conv, info
    except Exception as e:
        raise RuntimeError("এই অডিওটি ডাউনলোড করা যাবে না বা সুরক্ষিত।") from e
    raise FileNotFoundError("Audio file not found after yt-dlp run.")

# ----------------- TELEGRAM HANDLERS -----------------
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip() or "বন্ধু"

    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("ℹ️ ডেভেলপার ইনফরমেশন", callback_data="developer_info")
    )

    txt = (
        f"👋 হ্যালো {full_name}!\n\n"
        "আমি 🤖 Doob Ai, আপনার ভিডিও ও অডিও ডাউনলোড সহকারী।\n\n"
        "🎥 আপনি শুধু ইউটিউব, টিকটক, ফেসবুক বা ইনস্টাগ্রামের লিংক পাঠান —\n"
        "তারপর আমি আপনাকে ভিডিও বা অডিও হিসেবে ডাউনলোডের অপশন দেবো।\n\n"
        "© 2025 | Developed by Salman Ai Ltd\n"
        "Managed by Salman Ahamed Robin"
    )

    bot.reply_to(message, txt, reply_markup=markup)

@bot.message_handler(func=lambda m: True, content_types=['text'])
def catch_all(message):
    tokens = message.text.strip().split()
    url_candidate = next((t for t in tokens if is_likely_url(t)), None)
    if not url_candidate:
        bot.reply_to(message, "📎 দয়া করে একটি সঠিক ভিডিও বা অডিও লিংক পাঠান।")
        return

    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("🎞️ ভিডিও (MP4)", callback_data=f"video|{url_candidate}"),
        InlineKeyboardButton("🎵 অডিও (MP3)", callback_data=f"audio|{url_candidate}")
    )
    bot.send_message(message.chat.id, "⬇️ আপনি কীভাবে ডাউনলোড করতে চান?", reply_markup=markup)

# ----------------- CALLBACK HANDLER -----------------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: CallbackQuery):
    unique = gen_temp_name("dl")
    try:
        if call.data == "developer_info":
            dev_text = (
                "👨‍💻 **Developer Information**\n\n"
                "🏢 Developed by: Salman Ai Ltd\n"
                "👤 Managed by: Salman Ahamed Robin\n"
                "📧 Contact: support@salmanailtd.com\n"
                "🌐 Website: https://salmanailtd.com\n\n"
                "© 2025 All Rights Reserved"
            )
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, dev_text, parse_mode="Markdown")
            return

        mode, url = call.data.split("|", 1)
        bot.edit_message_text("🔄 অনুগ্রহ করে অপেক্ষা করুন, ডাউনলোড শুরু হচ্ছে...", call.message.chat.id, call.message.message_id)
        out_template = str(TMP_DIR / (unique + ".%(ext)s"))

        if mode == "audio":
            result_path, info = ytdlp_download_audio_mp3(url, out_template)
            with open(result_path, "rb") as f:
                bot.send_document(call.message.chat.id, f, caption=f"{info.get('title','')} (MP3)")
        else:
            result_path, info = ytdlp_download_best(url, out_template)
            title = info.get('title') or unique
            filesize = os.path.getsize(result_path)
            with open(result_path, "rb") as f:
                if filesize <= 50 * 1024 * 1024:
                    bot.send_video(call.message.chat.id, f, caption=title)
                else:
                    bot.send_document(call.message.chat.id, f, caption=title)

        bot.send_message(call.message.chat.id, "✅ ডাউনলোড সম্পন্ন! ধন্যবাদ Doob Ai ব্যবহার করার জন্য 💙")
    except Exception as e:
        logger.exception("Error during download/upload")
        bot.send_message(call.message.chat.id, f"⚠️ একটি ত্রুটি ঘটেছে: {str(e)}")
    finally:
        # Clean up temp files
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
    print("🚀 Doob Ai Bot is running successfully...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("Bot stopped manually.")
    except Exception as e:
        logger.exception("Bot stopped unexpectedly: %s", e)