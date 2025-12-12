import os
import asyncio
from openai import OpenAI
from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)
from pydub import AudioSegment

# Load config from env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Please set TELEGRAM_TOKEN and OPENAI_API_KEY in environment variables. See .env.example")

client = OpenAI(api_key=OPENAI_API_KEY)

# In-memory user memory (simple). For production use persistent storage.
user_memory = {}
last_user_image = {}  # store last downloaded image path per user

def add_message(user_id: int, role: str, content: str):
    if user_id not in user_memory:
        user_memory[user_id] = []
    user_memory[user_id].append({"role": role, "content": content})
    # Keep memory bounded
    if len(user_memory[user_id]) > 40:
        user_memory[user_id] = user_memory[user_id][-40:]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id] = []
    menu = ReplyKeyboardMarkup(
        [["🧠 Reset Memory", "🔁 Hỏi lại"], ["📷 Gửi Ảnh", "🎤 Gửi Voice"], ["📁 Gửi File"]],
        resize_keyboard=True
    )
    await update.message.reply_text("Xin chào! Bot AI đã sẵn sàng. Chọn tác vụ từ menu hoặc gõ tin nhắn.", reply_markup=menu)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id] = []
    await update.message.reply_text("✅ Memory đã được reset.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    # If user pressed menu items (they are text), handle them
    if text in ["🧠 Reset Memory", "🔁 Hỏi lại", "📷 Gửi Ảnh", "🎤 Gửi Voice", "📁 Gửi File"]:
        return await menu_handler(update, context)

    add_message(user_id, "user", text)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # Call OpenAI Chat Completion
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # change to an available model in your account
            messages=user_memory[user_id]
        )
        reply = resp.choices[0].message["content"]
    except Exception as e:
        reply = "⚠️ Lỗi khi gọi OpenAI: " + str(e)

    # Save assistant message to memory and send with inline buttons
    add_message(user_id, "assistant", reply)
    await send_ai_reply(update, reply)

async def send_ai_reply(update_or_ctx, text: str):
    # update_or_ctx can be Update or Context, but we expect Update in our calls
    update = update_or_ctx if isinstance(update_or_ctx, Update) else update_or_ctx._update
    inline = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Hỏi lại", callback_data="retry"),
         InlineKeyboardButton("❌ Xoá memory", callback_data="clear")]
    ])
    await update.message.reply_text(text, reply_markup=inline)

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🧠 Reset Memory":
        await reset(update, context)
    elif text == "🔁 Hỏi lại":
        # Ask again last user message
        user_id = update.effective_user.id
        mem = user_memory.get(user_id, [])
        # find last user message
        last_user = None
        for m in reversed(mem):
            if m["role"] == "user":
                last_user = m["content"]
                break
        if last_user:
            # push it again, then call handler
            add_message(user_id, "user", last_user)
            await handle_text(update, context)
        else:
            await update.message.reply_text("Không có lịch sử để hỏi lại.")
    elif text == "📷 Gửi Ảnh":
        await update.message.reply_text("Hãy gửi 1 ảnh để bot lưu/ xử lý.")
    elif text == "🎤 Gửi Voice":
        await update.message.reply_text("Hãy gửi voice message.")
    elif text == "📁 Gửi File":
        await update.message.reply_text("Hãy gửi file (txt / md / json được ưu tiên).")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    f = await photo.get_file()
    path = f"downloads/image_{user_id}_{photo.file_unique_id}.jpg"
    os.makedirs("downloads", exist_ok=True)
    await f.download_to_drive(path)
    last_user_image[user_id] = path
    await update.message.reply_text("🖼️ Ảnh đã được lưu. Gõ /analyze để phân tích cơ bản (hoặc mô tả bạn muốn).")


async def analyze_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    path = last_user_image.get(user_id)
    if not path or not os.path.exists(path):
        await update.message.reply_text("Không tìm thấy ảnh đã gửi. Vui lòng gửi ảnh trước.")
        return
    await update.message.reply_text("Đang gửi ảnh cho AI phân tích (lưu ý: cần model Vision/Responses hỗ trợ ảnh).") 
    try:
        # NOTE: this is a placeholder: actual image understanding requires OpenAI Responses or Vision API.
        # Here we will send a simple prompt telling the model there's an image at filename, and ask for general guidance.
        with open(path, "rb") as f:
            b = f.read()
        prompt = f"Người dùng gửi 1 ảnh (đã lưu tên file). Hãy đưa ra các gợi ý phân tích nếu bạn không thể xem ảnh trực tiếp. "                  f"Nếu có thể phân tích ảnh, mô tả các đối tượng có thể xuất hiện và câu hỏi gợi ý cho người dùng."
        # We append system + user messages to memory and call chat model
        add_message(user_id, "user", "Hãy phân tích ảnh tôi vừa gửi.")
        add_message(user_id, "system", "Ảnh được lưu tại server. (binary not sent).")
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=user_memory[user_id] + [{"role":"user","content":prompt}]
        )
        reply = resp.choices[0].message["content"]
    except Exception as e:
        reply = "Lỗi khi phân tích ảnh: " + str(e)
    add_message(user_id, "assistant", reply)
    await update.message.reply_text(reply)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    voice = update.message.voice or update.message.audio
    if not voice:
        await update.message.reply_text("Không tìm thấy voice.")
        return
    f = await voice.get_file()
    ogg_path = f"downloads/voice_{user_id}_{voice.file_unique_id}.ogg"
    wav_path = ogg_path.replace(".ogg", ".wav")
    os.makedirs("downloads", exist_ok=True)
    await f.download_to_drive(ogg_path)
    try:
        # convert ogg -> wav using pydub (ffmpeg required)
        AudioSegment.from_file(ogg_path).export(wav_path, format="wav")
        await update.message.reply_text("Đang chuyển giọng nói sang văn bản...")
        # send to OpenAI whisper transcription endpoint
        transcription = client.audio.transcriptions.create(
            model="gpt-4o-transcribe", # change if needed
            file=open(wav_path, "rb")
        )
        text = transcription.text
        add_message(user_id, "user", text)
        # get chat reply
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=user_memory[user_id]
        )
        reply = resp.choices[0].message["content"]
        add_message(user_id, "assistant", reply)
        await update.message.reply_text(f"🗣️ Bạn nói: {text}\n\n🤖 Bot trả lời: {reply}")
    except Exception as e:
        await update.message.reply_text("Lỗi khi xử lý voice: " + str(e))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document
    f = await doc.get_file()
    os.makedirs("downloads", exist_ok=True)
    path = f"downloads/{doc.file_name}"
    await f.download_to_drive(path)
    # Try to read text files (txt, md, json) and summarize
    try:
        if doc.file_name.lower().endswith(('.txt', '.md', '.json')):
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read(100000)  # limit
            add_message(user_id, "user", f"Đã gửi file: {doc.file_name}")
            # ask OpenAI to summarize
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":"Bạn là trợ lý tóm tắt file."},
                          {"role":"user","content": "Hãy tóm tắt nội dung dưới đây:\n\n" + content}]
            )
            reply = resp.choices[0].message["content"]
        else:
            reply = "File đã được lưu. Hiện tại bot chỉ tự tóm tắt file text (txt, md, json)."
    except Exception as e:
        reply = "Lỗi khi đọc file: " + str(e)
    add_message(user_id, "assistant", reply)
    await update.message.reply_text(reply)


async def inline_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "retry":
        # Resend last user message content
        mem = user_memory.get(user_id, [])
        last_user = None
        for m in reversed(mem):
            if m["role"] == "user":
                last_user = m["content"]
                break
        if last_user:
            add_message(user_id, "user", last_user)
            # create a fake Update with last_user as message to reuse handle_text
            class FakeMsg: pass
            fake = FakeMsg()
            fake.message = query.message
            fake.message.text = last_user
            fake.message.from_user = query.from_user
            fake.message.chat = query.message.chat
            await handle_text(fake, context)
        else:
            await query.message.reply_text("Không có tin nhắn trước để hỏi lại.")
    elif query.data == "clear":
        user_memory[user_id] = []
        await query.message.reply_text("Memory đã được xoá.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start - Bắt đầu\n/reset - Xoá memory\n/analyze - Phân tích ảnh vừa gửi\n/help - Hướng dẫn\n\nGửi text/voice/image/file để bot xử lý.")


async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("analyze", analyze_image))
    app.add_handler(CommandHandler("help", help_cmd))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Regex("🧠|🔁|📷|🎤|📁"), menu_handler))

    app.add_handler(CallbackQueryHandler(inline_button_handler))

    print("Bot AI đang chạy...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
