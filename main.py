import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from config import TELEGRAM_BOT_TOKEN
from services import (call_gemini_ocr, call_unstructured_partition, call_openrouter_summarize, call_openai_transcribe,
                      chunk_text, add_to_vector_store, get_rag_answer, clear_vector_store)

# --- Basic Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.DEBUG)

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
    await update.message.reply_html(rf"Hi {user.mention_html()}! Send me a document or an audio file.")

async def _process_file(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str, file_name: str) -> None:
    """
    A generic helper function to process a file (document or photo).
    Downloads the file, performs OCR, and presents action buttons.
    """
    progress_message = await update.message.reply_text(f"⏳ Đang xử lý file: {file_name}\n[10%] Đã nhận file.")
    
    file = await context.bot.get_file(file_id)
    original_file_path = f"downloads/{file_id}_{file_name}"
    os.makedirs(os.path.dirname(original_file_path), exist_ok=True)
    
    try:
        await progress_message.edit_text(f"⏳ Đang xử lý file: {file_name}\n[25%] Đang tải file xuống...")
        await file.download_to_drive(original_file_path)

        await progress_message.edit_text(f"⏳ Đang xử lý file: {file_name}\n[50%] Đã tải xong, đang trích xuất văn bản...")
        
        # Use the best tool for the job: Gemini for visual files, unstructured for others.
        if file_name.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
            full_text = await call_gemini_ocr(original_file_path)
        else: # For .docx, .pptx, etc.
            full_text = await call_unstructured_partition(original_file_path)

        # CRITICAL CHECK: Stop immediately if partitioning failed.
        if full_text is None or not full_text.strip() or full_text.strip().startswith("[Error:"):
            error_message = full_text if (full_text and full_text.strip()) else "Không thể trích xuất văn bản từ tài liệu này."
            await progress_message.edit_text(error_message)
            return

        await progress_message.edit_text(f"✅ Trích xuất hoàn tất. Đang xây dựng cơ sở tri thức... [75%]")

        # Use a single collection per user
        collection_name = f"user_{update.effective_user.id}"
        chunks = await asyncio.to_thread(chunk_text, full_text)
        
        # Create metadata for each chunk, pointing back to the source file
        metadatas = [{"source": file_name} for _ in chunks]
        
        await asyncio.to_thread(add_to_vector_store, chunks, metadatas, collection_name)

        # Set user data for the chat session
        context.user_data['collection_name'] = collection_name
        context.user_data['chat_history'] = []
        context.user_data['selected_model'] = context.user_data.get('selected_model', DEFAULT_MODEL)

        keyboard = [
            [InlineKeyboardButton("❓ Trò chuyện với tài liệu", callback_data='chat_with_doc')],
            [InlineKeyboardButton("Chọn Model", callback_data='select_model')],
            [InlineKeyboardButton("Thoát", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await progress_message.edit_text(            
            f"✅ Đã thêm nội dung từ file '{file_name}' vào cơ sở tri thức của bạn. Bạn muốn làm gì tiếp theo?",
            reply_markup=reply_markup
        )

    finally:
        # Clean up the downloaded file
        if os.path.exists(original_file_path):
            os.remove(original_file_path)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming documents by calling the generic file processor."""
    document = update.message.document
    file_name = document.file_name
    
    ALLOWED_EXTENSIONS = ('.pdf', '.png', '.jpg', '.jpeg', '.docx', '.pptx')
    if not file_name.lower().endswith(ALLOWED_EXTENSIONS):
        await update.message.reply_text(f"Sorry, I can only process the following file types: {', '.join(ALLOWED_EXTENSIONS)}")
        return

    await _process_file(update, context, document.file_id, file_name)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles incoming photos by selecting the largest one and calling the
    generic file processor.
    """
    photo_file = update.message.photo[-1] # Get the largest photo
    file_name = f"{photo_file.file_id}.jpg"
    await _process_file(update, context, photo_file.file_id, file_name)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles all button presses from inline keyboards."""
    query = update.callback_query
    await query.answer()
    command = query.data
    logger.info(f"Button press received: {command}")

    # Clear chat mode if user interacts with buttons
    context.user_data['chat_mode'] = False

    if command == 'chat_with_doc':
        context.user_data['chat_mode'] = True
        context.user_data['chat_history'] = [] # Reset history for new chat session
        await query.edit_message_text(
            text="✅ Sẵn sàng! Mời bạn đặt câu hỏi về các tài liệu đã tải lên.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Kết thúc trò chuyện", callback_data='end_chat')]])
        )

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
            [InlineKeyboardButton("❓ Trò chuyện với tài liệu", callback_data='chat_with_doc')],
            [InlineKeyboardButton("Thoát", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"Model đã được chọn: {model_name}. Quay lại menu chính.", reply_markup=reply_markup)

    elif command == 'cancel':
        await query.edit_message_text(text="Đã hủy. Gửi file mới để bắt đầu lại.")
        context.user_data.clear()
    
    elif command == 'end_chat':
        await query.edit_message_text(text="Đã kết thúc phiên trò chuyện. Gửi file mới để bắt đầu lại.")
        # Clear only chat-related data
        context.user_data.pop('collection_name', None)
        context.user_data.pop('chat_history', None)
        context.user_data.pop('chat_mode', None)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears the user's knowledge base."""
    collection_name = f"user_{update.effective_user.id}"
    try:
        await asyncio.to_thread(clear_vector_store, collection_name)
        context.user_data.clear()
        await update.message.reply_text("✅ Cơ sở tri thức của bạn đã được xóa sạch. Bạn có thể bắt đầu lại bằng cách gửi một tài liệu mới.")
    except Exception as e:
        logger.error(f"Error clearing collection {collection_name}: {e}")
        await update.message.reply_text("Có lỗi xảy ra khi xóa cơ sở tri thức. Có thể bạn chưa có dữ liệu nào.")





async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a detailed help message explaining how to use the bot."""
    help_text = """<b>🌟 Chào mừng bạn đến với Bot Trợ Lý Đa Năng! 🌟</b>
    
Tôi có thể giúp bạn với nhiều loại tệp khác nhau.
    
<b>Cách sử dụng:</b>
1.  <b>Với tài liệu (<code>.pdf</code>, <code>.docx</code>, v.v.):</b> Gửi file cho tôi, tôi sẽ trích xuất văn bản và bạn có thể yêu cầu tôi tóm tắt nội dung đó (*).
2.  <b>Với âm thanh (file audio, tin nhắn thoại) (*):</b> Gửi file hoặc ghi âm một tin nhắn thoại, tôi sẽ chuyển đổi giọng nói thành văn bản cho bạn.
    
<b>Các mô hình AI hỗ trợ tóm tắt (*):</b>
- Claude 3.5 Sonnet (Mặc định)
- Gemini 1.5 Flash
- GPT-4o Mini
    
<b>Mô hình chuyển đổi giọng nói thành văn bản (*):</b>
- OpenAI Whisper
    
---
<b>Lưu ý quan trọng:</b>
Các tính năng có đánh dấu (*) sẽ sử dụng API của bên thứ ba (OpenRouter, OpenAI) và có thể phát sinh chi phí. Vui lòng thử nghiệm một cách hợp lý để tiết kiệm chi phí nhé!
    
Hãy gửi file đầu tiên của bạn để bắt đầu nào! 🚀"""
    await update.message.reply_html(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles plain text messages by asking the user to send a file instead."""
    if context.user_data.get('chat_mode'):
        question = update.message.text
        collection_name = context.user_data.get('collection_name')
        chat_history = context.user_data.get('chat_history', [])
        model = context.user_data.get('selected_model', DEFAULT_MODEL)

        if not collection_name:
            await update.message.reply_text("Lỗi: Cơ sở tri thức không tồn tại. Vui lòng gửi lại file.")
            return

        progress_message = await update.message.reply_text("⏳ AI đang suy nghĩ...")
        answer = await get_rag_answer(collection_name, question, chat_history, model)
        
        # Update chat history
        chat_history.append(("human", question))
        chat_history.append(("ai", answer))
        
        await progress_message.edit_text(answer, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Kết thúc trò chuyện", callback_data='end_chat')]]))
    else:
        await update.message.reply_text("Vui lòng gửi một tài liệu hoặc file audio để tôi xử lý.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming audio or voice messages for transcription."""
    audio_obj = update.message.audio or update.message.voice
    file_name = audio_obj.file_name if hasattr(audio_obj, 'file_name') and audio_obj.file_name else f"voice_note_{audio_obj.file_id}.ogg"

    progress_message = await update.message.reply_text(f"⏳ Đang xử lý file audio: {file_name}")

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
    application.add_handler(CommandHandler("clear", clear_command))

    # on non command i.e message - handle the message from user
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # on receiving a document
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # on receiving a photo
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # on receiving audio
    application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))

    # handle button clicks
    application.add_handler(CallbackQueryHandler(button_handler))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting... Press Ctrl-C to stop.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
