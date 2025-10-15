import os
import logging
import asyncio
import httpx
from typing import Optional
from docling.document_converter import DocumentConverter

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Environment & Service Configuration ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Service Call Functions ---

async def call_docling_ocr(file_path: str) -> Optional[str]:
    """
    Processes a document file using the Docling library to perform OCR.

    This function runs the synchronous Docling conversion in a separate thread
    to avoid blocking the asyncio event loop.

    Args:
        file_path: The local path to the document file to process.

    Returns:
        The extracted text in Markdown format, or an error message string if
        the conversion fails.
    """
    logger.info(f"Processing {file_path} with Docling library...")
    try:
        def convert_sync():
            converter = DocumentConverter()
            result = converter.convert(file_path)
            return result.document.export_to_markdown()
        return await asyncio.to_thread(convert_sync)
    except Exception as e:
        logger.error(f"An unexpected error occurred during Docling conversion: {e}")
        return f"[Error: Docling failed to process {os.path.basename(file_path)}]"

async def call_openrouter_summarize(text: str, model: str) -> Optional[str]:
    """
    Summarizes the given text using a specified model via the OpenRouter API.
    Uses httpx for non-blocking asynchronous requests.

    Args:
        text: The text content to be summarized.
        model: The model identifier to use for summarization.

    Returns:
        The summarized text as a string, or an error/skip message.
    """
    if not OPENROUTER_API_KEY:
        return "[Skipping summarization: OPENROUTER_API_KEY is not set]"
    logger.info(f"Sending text ({len(text)} chars) to OpenRouter using model {model}...")
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are an expert assistant that summarizes long texts into a concise, easy-to-read summary in Vietnamese."},
                        {"role": "user", "content": f"Please summarize the following content:\n\n{text}"}
                    ]
                }
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except httpx.RequestError as e:
            logger.error(f"An HTTP error occurred during summarization: {e}")
            return f"[Error: Summarization failed due to a network issue. Details: {e}]"
        except Exception as e:
            logger.error(f"An unexpected error occurred during summarization: {e}")
            return f"[Error: Summarization failed. Details: {e}]"

async def call_openai_transcribe(file_path: str) -> Optional[str]:
    """
    Transcribes an audio file using the OpenAI Whisper API.
    Uses httpx for non-blocking asynchronous requests.

    Args:
        file_path: The local path to the audio file to transcribe.

    Returns:
        The transcribed text as a string, or an error/skip message.
    """
    if not OPENAI_API_KEY:
        return "[Skipping transcription: OPENAI_API_KEY is not set]"
    logger.info(f"Transcribing {file_path} with OpenAI Whisper API...")

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            with open(file_path, "rb") as audio_file:
                files = {'file': (os.path.basename(file_path), audio_file), 'model': (None, 'whisper-1')}
                response = await client.post("https://api.openai.com/v1/audio/transcriptions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, files=files)
            response.raise_for_status()
            return response.json()['text']
        except Exception as e:
            logger.error(f"An unexpected error occurred during transcription: {e}")
            error_details = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                except ValueError:
                    error_details = e.response.text
            return f"[Error: Transcription failed. Details: {error_details}]"