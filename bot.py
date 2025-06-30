import os
import tempfile
import asyncio
import subprocess
import time
import traceback
import re
from collections import defaultdict

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp
from dotenv import load_dotenv
load_dotenv()  # 🔐 Load variables from .env
# === Config ===

# ✅ Use environment variable for security (Render will set this in dashboard)
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# ✅ Use /tmp for output dir (safe for local & cloud)
OUTPUT_DIR = "/tmp/StoredSongs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ✅ Dynamically pick ffmpeg path
FFMPEG_BIN = os.environ.get("FFMPEG_BIN") or "ffmpeg"

# === Rate Limiter ===
user_download_log = defaultdict(list)

# === Clean YouTube URL ===
def clean_youtube_url(url: str) -> str:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url

# === Sanitize File Name ===
def safe_filename(title: str) -> str:
    # Remove invalid characters for cross-OS safety
    return re.sub(r'[\\/:"*?<>|]+', '-', title)

# === Cleanup ===
async def cleanup_file_later(path):
    await asyncio.sleep(1800)  # 30 min
    try:
        os.remove(path)
        print(f"🧼 Deleted: {path}")
    except Exception as e:
        print(f"🧹 Could not delete file: {e}")

# === /start with UI ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎵 How to Use", callback_data="how_to_use")],
        [InlineKeyboardButton("🎶 Try a Sample", callback_data="sample")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎧 *Welcome to AudioGod!*\n\nSend a YouTube link and get your music in MP3 or M4A.\n\nNo typing needed — tap below 👇",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# === Button Clicks ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "how_to_use":
        await query.message.reply_text("📌 Just paste a YouTube song link here. I’ll convert & send you MP3 and M4A!")
    elif query.data == "sample":
        await query.message.reply_text("📽️ Try this:\nhttps://www.youtube.com/watch?v=2Vv-BfVoq4g")

# === YouTube Link Handler ===
async def handle_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    original_url = update.message.text
    url = clean_youtube_url(original_url)
    user_id = update.message.from_user.id

    # ✅ Rate limit
    now = time.time()
    recent = [t for t in user_download_log[user_id] if now - t < 300]
    if len(recent) >= 5:
        await update.message.reply_text("⏱️ 5 downloads per 5 min limit. Please try again later.")
        return
    user_download_log[user_id] = recent + [now]

    # Show progress
    progress_msg = await update.message.reply_text("📥 Downloading...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                video_title = info.get("title", "AudioGod Track")
                safe_title = safe_filename(video_title)

            await progress_msg.edit_text("🎧 Converting to MP3 & M4A...")

            for ext in ['mp3', 'm4a']:
                output_path = os.path.join(OUTPUT_DIR, f"{safe_title}.{ext}")
                command = [
                    FFMPEG_BIN, "-y",
                    "-i", filename,
                    output_path
                ]
                subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                await update.message.reply_audio(
                    audio=open(output_path, 'rb'),
                    filename=os.path.basename(output_path),
                    caption=f"🎶 *{video_title}* ({ext.upper()})",
                    parse_mode="Markdown"
                )
                asyncio.create_task(cleanup_file_later(output_path))

            await progress_msg.edit_text("✅ Done! Enjoy your music 🔥")

    except Exception as e:
        traceback.print_exc()
        await progress_msg.edit_text(f"⚠️ Error:\n{str(e)}")

# === /help ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Just paste a YouTube link. I’ll handle the rest! 🎵"
    )

# === Run Bot ===
def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set! Add it as an environment variable.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_link))
    print("🤖 AudioGod Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
