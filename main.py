import logging
import os
from typing import Optional
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from services import call_docling_ocr, call_openrouter_summarize, call_openai_transcribe

# --- Basic Setup ---
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.DEBUG)

# --- Environment & Service Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Please put your TELEGRAM_BOT_TOKEN in the .env file.")

# --- Model List ---
AVAILABLE_MODELS = {
    "Claude 3.5 Sonnet": "anthropic/claude-3.5-sonnet",
    "Gemini Flash 1.5": "google/gemini-1.5-flash",
    "GPT-4o Mini": "openai/gpt-4o-mini",
}
DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"

# --- Bot UI and Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(rf"Hi {user.mention_html()}! Send me a document or an audio file.", message_thread_id=15)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles incoming documents. Downloads the file, performs OCR, and presents
    the user with options to view content, summarize, or cancel.
    """
    document = update.message.document
    file_name = document.file_name
    
    ALLOWED_EXTENSIONS = ('.pdf', '.png', '.jpg', '.jpeg', '.docx', '.pptx')
    if not file_name.lower().endswith(ALLOWED_EXTENSIONS):
        await update.message.reply_text(f"Sorry, I can only process the following file types: {', '.join(ALLOWED_EXTENSIONS)}", message_thread_id=15)
        return

    progress_message = await update.message.reply_text(f"⏳ Đang xử lý file: {file_name}\n[10%] Đã nhận file.", message_thread_id=15)
    
    file = await context.bot.get_file(document.file_id)
    original_file_path = f"downloads/{document.file_id}_{file_name}"
    os.makedirs(os.path.dirname(original_file_path), exist_ok=True)
    
    try:
        await progress_message.edit_text(f"⏳ Đang xử lý file: {file_name}\n[25%] Đang tải file xuống...")
        await file.download_to_drive(original_file_path)

        await progress_message.edit_text(f"⏳ Đang xử lý file: {file_name}\n[50%] Đã tải xong, đang trích xuất văn bản...")
        full_text = await call_docling_ocr(original_file_path)

        if full_text is None or not full_text.strip():
             await progress_message.edit_text("Không thể trích xuất văn bản từ tài liệu này.")
             return

        context.user_data['full_text'] = full_text
        context.user_data['selected_model'] = context.user_data.get('selected_model', DEFAULT_MODEL)

        keyboard = [
            [InlineKeyboardButton("Hiển thị nội dung", callback_data='show_content')],
            [InlineKeyboardButton("Tóm tắt nội dung", callback_data='summarize')],
            [InlineKeyboardButton("Chọn Model", callback_data='select_model')],
            [InlineKeyboardButton("Thoát", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await progress_message.edit_text(
            f"✅ Trích xuất hoàn tất cho file: {file_name}\n(Tìm thấy {len(full_text)} ký tự). Bạn muốn làm gì tiếp theo?",
            reply_markup=reply_markup
        )

    finally:
        # Clean up the downloaded file
        if os.path.exists(original_file_path):
            os.remove(original_file_path)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles all button presses from inline keyboards."""
    query = update.callback_query
    await query.answer()
    command = query.data
    logger.info(f"Button press received: {command}")

    if command == 'show_content':
        full_text = context.user_data.get('full_text')
        if not full_text:
            await query.message.reply_text("Lỗi: Không có nội dung để hiển thị.")
            return
        
        # Truncate for display and send as a new message
        display_text = full_text[:4000]
        if len(full_text) > 4000:
            display_text += "\n\n[...Nội dung quá dài, chỉ hiển thị 4000 ký tự đầu tiên...]"
        
        # Send content in a new message
        await query.message.reply_text(f"""--- NỘI DUNG ĐẦY ĐỦ ---\n\n{display_text}""")
        
        # Edit the original message to confirm and keep buttons
        await query.edit_message_text(
            text=f"Nội dung đã được hiển thị trong tin nhắn mới. Bạn muốn làm gì tiếp theo?",
            reply_markup=query.message.reply_markup
        )

    elif command == 'summarize':
        full_text = context.user_data.get('full_text')
        selected_model_id = context.user_data.get('selected_model', DEFAULT_MODEL)
        if not full_text:
            await query.edit_message_text(text="Lỗi: Không có văn bản để tóm tắt.")
            return

        # Get model name for display
        model_name = [name for name, mid in AVAILABLE_MODELS.items() if mid == selected_model_id][0]

        await query.edit_message_text(text=f"⏳ Đang tóm tắt bằng model {model_name}... [80%]")
        summary = await call_openrouter_summarize(full_text, selected_model_id)
        
        final_summary = summary or "Không thể tạo tóm tắt."
        await query.edit_message_text(text=f"✅ Tóm tắt hoàn tất! [100%]\n\n---\n{final_summary}")
        context.user_data.clear()

    elif command == 'select_model':
        keyboard = [[InlineKeyboardButton(name, callback_data=f'set_model:{model_id}')] for name, model_id in AVAILABLE_MODELS.items()]
        keyboard.append([InlineKeyboardButton("Thoát", callback_data='cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Vui lòng chọn một model:", reply_markup=reply_markup)

    elif command.startswith('set_model:'):
        model_id = command.split(':', 1)[1]
        model_name = [name for name, mid in AVAILABLE_MODELS.items() if mid == model_id][0]
        context.user_data['selected_model'] = model_id
        keyboard = [
            [InlineKeyboardButton("Tóm tắt nội dung", callback_data='summarize')],
            [InlineKeyboardButton("Thoát", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"Model đã được chọn: {model_name}. Bạn có muốn tóm tắt không?", reply_markup=reply_markup)

    elif command == 'cancel':
        await query.edit_message_text(text="Đã hủy. Gửi file mới để bắt đầu lại.")
        context.user_data.clear()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a detailed help message explaining how to use the bot."""
    help_text = """<b>🌟 Chào mừng bạn đến với Bot Trợ Lý Đa Năng! 🌟</b>

Tôi có thể giúp bạn với nhiều loại tệp khác nhau.

<b>Cách sử dụng:</b>
1. <b>Với tài liệu (<code>.pdf</code>, <code>.docx</code>, v.v.):</b> Gửi file cho tôi, tôi sẽ trích xuất văn bản và bạn có thể yêu cầu tôi tóm tắt.
2. <b>Với âm thanh (file audio, tin nhắn thoại):</b> Gửi file hoặc ghi âm một tin nhắn thoại, tôi sẽ gỡ băng và gửi lại văn bản cho bạn.

<b>Các mô hình AI hỗ trợ tóm tắt:</b>
- Claude 3.5 Sonnet (Mặc định)
- Gemini 1.5 Flash
- GPT-4o Mini

<b>Mô hình gỡ băng:</b>
- OpenAI Whisper

Hãy gửi file đầu tiên của bạn để bắt đầu nào!"""
    await update.message.reply_html(help_text, message_thread_id=15)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles plain text messages by asking the user to send a file instead."""
    await update.message.reply_text("Please send me a document or an audio file to process.", message_thread_id=15)

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming audio or voice messages for transcription."""
    audio_obj = update.message.audio or update.message.voice
    file_name = audio_obj.file_name if hasattr(audio_obj, 'file_name') and audio_obj.file_name else f"voice_note_{audio_obj.file_id}.ogg"

    progress_message = await update.message.reply_text(f"⏳ Đang xử lý file audio: {file_name}", message_thread_id=15)

    file = await context.bot.get_file(audio_obj.file_id)
    original_file_path = f"downloads/{audio_obj.file_id}_{file_name}"
    os.makedirs(os.path.dirname(original_file_path), exist_ok=True)

    try:
        await progress_message.edit_text(f"⏳ Đang tải file audio: {file_name}...")
        await file.download_to_drive(original_file_path)

        await progress_message.edit_text(f"⏳ Đã tải xong, đang gỡ băng: {file_name}...")
        transcript = await call_openai_transcribe(original_file_path)

        final_transcript = transcript or "Không thể gỡ băng file audio này."
        await progress_message.edit_text(f"✅ Gỡ băng hoàn tất!\n\n---\n{final_transcript}")

    except Exception as e:
        logger.error(f"Error processing audio file: {e}")
        await progress_message.edit_text(f"Đã xảy ra lỗi khi xử lý file audio của bạn.")
    finally:
        # Clean up the downloaded file
        if os.path.exists(original_file_path):
            os.remove(original_file_path)

def main() -> None:
    """Sets up the application and starts the bot polling cycle."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - handle the message from user
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # on receiving a document
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # on receiving audio
    application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))

    # handle button clicks
    application.add_handler(CallbackQueryHandler(button_handler))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting... Press Ctrl-C to stop.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
