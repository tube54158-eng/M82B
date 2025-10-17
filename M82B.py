#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M82B.py - Doob Ai Telegram Downloader Bot (cookie-free, Render-ready worker)
Demo token embedded as requested (only for testing). Do NOT push this file with token to public repos.
"""

import os
import uuid
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from yt_dlp import YoutubeDL

# ---------------- CONFIG ----------------
# DEMO token (you provided)
BOT_TOKEN = "8001674280:AAE51NTsJEM7Dyp2vnKbQUQ25laLnZHynhI"

if not BOT_TOKEN:
    raise SystemExit("ERROR: BOT_TOKEN not set.")

# tmp directory for downloads
TMP_DIR = Path("./tmp_dl")
TMP_DIR.mkdir(exist_ok=True, parents=True)

# Telegram file send threshold
TG_VIDEO_LIMIT = 50 * 1024 * 1024  # 50 MB

# Optional: restrict who can use the bot (comma-separated telegram user ids), leave empty to allow all
ALLOWED_USERS_ENV = os.environ.get("ALLOWED_USERS", "").strip()
ALLOWED_USERS = set()
if ALLOWED_USERS_ENV:
    for part in ALLOWED_USERS_ENV.split(","):
        try:
            ALLOWED_USERS.add(int(part.strip()))
        except Exception:
            pass

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("DoobAiDemo")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ---------------- helpers ----------------
def gen_temp_name(prefix: str = "dl") -> str:
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
            logger.warning("Failed to remove %s: %s", p, e)

def user_allowed(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS

def is_likely_url(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    keywords = ["youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com", "x.com", "twitter.com"]
    return any(k in t for k in keywords)

# ---------------- yt-dlp helpers ----------------
def build_ytdlp_opts(out_template: str, is_audio: bool = False) -> dict:
    opts = {
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "continuedl": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "allow_unplayable_formats": True,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    }

    if is_audio:
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]
        })
    else:
        opts.update({
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]
        })

    return opts

def ytdlp_download(url: str, out_template: str, is_audio: bool = False):
    opts = build_ytdlp_opts(out_template, is_audio=is_audio)
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fn = ydl.prepare_filename(info)
            base = str(Path(fn).with_suffix(''))
            candidates = [base + ext for ext in [".mp4", ".mkv", ".webm", ".mp3", ".m4a"]]
            candidates.append(fn)
            for cand in candidates:
                if cand and Path(cand).exists():
                    return str(Path(cand)), info
            if Path(fn).exists():
                return str(Path(fn)), info
            raise FileNotFoundError("Downloaded file not found after yt-dlp run.")
    except Exception as e:
        msg = str(e)
        if "Sign in to confirm your age" in msg or "age-restricted" in msg or "Login" in msg:
            raise RuntimeError("age_restricted")
        raise

# ---------------- Telegram handlers ----------------
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    if not user_allowed(message.from_user.id):
        bot.reply_to(message, "দুঃখিত — আপনার এই বট ব্যবহারের অনুমতি নেই।")
        return
    first = message.from_user.first_name or ""
    last = message.from_user.last_name or ""
    full = (first + " " + last).strip() or "বন্ধু"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("ℹ️ Developer Info", callback_data="dev_info"))
    text = (
        f"👋 হ্যালো {full}!\n\n"
        "আমি 🤖 Doob Ai — ইন্সট্যান্স (cookie-free)।\n"
        "লিংক পাঠান, আমি ভিডিও বা অডিও হিসেবে ডাউনলোডের অপশন দেবো।\n\n"
        "নোট: এই ইনস্ট্যান্সে কুকিজ ব্যবহার করা হয় না; তাই age‑restricted ভিডিও ডাউনলোড নাও হতে পারে।"
    )
    bot.reply_to(message, text, reply_markup=markup)

@bot.message_handler(func=lambda m: True, content_types=['text'])
def catch_all(message):
    if not user_allowed(message.from_user.id):
        bot.reply_to(message, "দুঃখিত — আপনার অনুমতি নেই।")
        return

    tokens = message.text.strip().split()
    url_candidate = next((t for t in tokens if is_likely_url(t)), None)
    if not url_candidate:
        bot.reply_to(message, "📎 অনুগ্রহ করে একটি সঠিক ভিডিও/অডিও লিংক পাঠান।")
        return

    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("🎞️ Video (MP4)", callback_data=f"video|{url_candidate}"),
        InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"audio|{url_candidate}")
    )
    markup.add(InlineKeyboardButton("💡 কেন কিছু ভিডিও ডাউনলোড হবে না", callback_data="why"))
    bot.send_message(message.chat.id, "নিচ থেকে বিকল্প সিলেক্ট করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: CallbackQuery):
    if not user_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "আপনার অনুমতি নেই।")
        return

    data = call.data
    if data == "dev_info":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
                         "Developer: Salman Ai Ltd\nManaged by: Salman Ahamed Robin")
        return
    if data == "why":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
                         "কিছু ভিডিও age-restricted বা private হতে পারে — এধরনের ভিডিওর জন্য লগইন/কুকি দরকার। এই public instance এ আমরা নিরাপত্তার কারণে কুকি ব্যবহার করছি না।")
        return

    unique = gen_temp_name("dl")
    try:
        mode, url = data.split("|", 1)
        bot.edit_message_text("🔄 ডাউনলোড শুরু হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...", call.message.chat.id, call.message.message_id)
        out_template = str(TMP_DIR / (unique + ".%(ext)s"))
        is_audio = (mode == "audio")

        result_path, info = ytdlp_download(url, out_template, is_audio=is_audio)

        title = info.get('title') or Path(result_path).name
        filesize = Path(result_path).stat().st_size if Path(result_path).exists() else 0

        with open(result_path, "rb") as f:
            if filesize <= TG_VIDEO_LIMIT and not is_audio:
                bot.send_video(call.message.chat.id, f, caption=title)
            else:
                bot.send_document(call.message.chat.id, f, caption=title)

        bot.send_message(call.message.chat.id, "✅ ডাউনলোড সম্পন্ন!")
    except RuntimeError as re:
        if str(re) == "age_restricted":
            bot.send_message(call.message.chat.id,
                             "⚠️ এই ভিডিওটি age-restricted বা লগইন প্রয়োজন।\n"
                             "এই public সার্ভারে কুকি ব্যবহৃত হয় না — তাই এটি ডাউনলোড হবে না।\n"
                             "আপনি চাইলে লোকালি বা trusted VPS-এ cookie দিয়ে ডাউনলোড করতে পারবেন।")
        else:
            bot.send_message(call.message.chat.id, f"⚠️ একটি ত্রুটি ঘটেছে: {str(re)}")
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
            except Exception:
                pass

# ---------------- RUN ----------------
if __name__ == "__main__":
    logger.info("Doob Ai Demo Bot starting... (cookie-free public mode)")
    logger.info("Allowed users: %s", ALLOWED_USERS or "ALL")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
    except Exception:
        logger.exception("Bot stopped unexpectedly.")