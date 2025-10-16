#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import uuid
import shutil
import logging
from pathlib import Path
from datetime import datetime
import subprocess

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from yt_dlp import YoutubeDL

BOT_TOKEN = "8001674280:AAERnecjl4roU04UT4B2VkMLb3bQPKKgu4c"
TMP_DIR = Path("./tmp_dl")
TMP_DIR.mkdir(exist_ok=True, parents=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

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
        except:
            pass

def is_likely_url(text: str):
    keywords = ["youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com"]
    return any(k in text.lower() for k in keywords)

def ytdlp_download_best(url: str, out_template: str):
    opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fn = ydl.prepare_filename(info)
            base = os.path.splitext(fn)[0]
            mp4_file = base + ".mp4"
            if os.path.exists(mp4_file):
                return mp4_file, info
            return fn, info
    except Exception:
        raise RuntimeError("এই ভিডিওটি ডাউনলোড করা যাবে না বা এটি সুরক্ষিত।")

def ytdlp_download_audio_mp3(url: str, out_template: str):
    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{"key": "FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}],
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fn = ydl.prepare_filename(info)
            mp3_file = os.path.splitext(fn)[0] + ".mp3"
            if os.path.exists(mp3_file):
                return mp3_file, info
            return fn, info
    except Exception:
        raise RuntimeError("এই অডিওটি ডাউনলোড করা যাবে না বা এটি সুরক্ষিত।")

# ---------------- Handlers ----------------
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip() or "বন্ধু"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("ℹ️ ডেভেলপার ইনফরমেশন", callback_data="developer_info"))
    txt = (
        f"👋 হ্যালো {full_name}!\n\n"
        "আমি 🤖 Doob Ai, আপনার ভিডিও ও অডিও ডাউনলোড সহকারী।\n\n"
        "🎥 শুধু লিংক পাঠান, আমি আপনাকে ভিডিও বা অডিও হিসেবে ডাউনলোডের অপশন দেবো।\n\n"
        "↓"
 
    )
    bot.reply_to(message, txt, reply_markup=markup)

@bot.message_handler(func=lambda m: True, content_types=['text'])
def catch_all(message):
    url_candidate = next((t for t in message.text.strip().split() if is_likely_url(t)), None)
    if not url_candidate:
        bot.reply_to(message, "📎 দয়া করে একটি সঠিক ভিডিও বা অডিও লিংক পাঠান।")
        return
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎞️ ভিডিও (MP4)", callback_data=f"video|{url_candidate}"),
        InlineKeyboardButton("🎵 অডিও (MP3)", callback_data=f"audio|{url_candidate}")
    )
    bot.send_message(message.chat.id, "⬇️ আপনি কীভাবে ডাউনলোড করতে চান?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: CallbackQuery):
    unique = gen_temp_name()
    try:
        if call.data == "developer_info":
            dev_text = (
                "👨‍💻 Developer Information\n"
                "🏢 Developed by: Salman Ai Ltd\n"
                "👤 Managed by: Salman Ahamed Robin\n"
                "© 2025 All Rights Reserved"
            )
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, dev_text)
            return

        mode, url = call.data.split("|",1)
        bot.edit_message_text("🔄 ডাউনলোড শুরু হচ্ছে...", call.message.chat.id, call.message.message_id)
        out_template = str(TMP_DIR / (unique + ".%(ext)s"))

        if mode == "audio":
            result_path, info = ytdlp_download_audio_mp3(url, out_template)
            with open(result_path, "rb") as f:
                bot.send_document(call.message.chat.id, f, caption=f"{info.get('title','')} (MP3)")
        else:
            result_path, info = ytdlp_download_best(url, out_template)
            title = info.get('title','')
            filesize = os.path.getsize(result_path)
            with open(result_path, "rb") as f:
                if filesize <= 50*1024*1024:
                    bot.send_video(call.message.chat.id, f, caption=title)
                else:
                    bot.send_document(call.message.chat.id, f, caption=title)

        bot.send_message(call.message.chat.id, "✅ ডাউনলোড সম্পন্ন! ধন্যবাদ Doob Ai ব্যবহার করার জন্য 💙")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ একটি ত্রুটি ঘটেছে: {str(e)}")
    finally:
        clean_files(*TMP_DIR.glob(f"{unique}*"))

# ---------------- Run ----------------
if __name__=="__main__":
    print("🚀 Doob Ai Bot running...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("Bot stopped manually.")
    except Exception as e:
        logging.exception("Bot stopped unexpectedly: %s", e)