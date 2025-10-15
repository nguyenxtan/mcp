import logging
import asyncio
import os
import httpx
import fitz  # PyMuPDF
import base64
from typing import Optional

from config import OPENROUTER_API_KEY, OPENAI_API_KEY
import chromadb
from unstructured.partition.auto import partition
from unstructured.documents.elements import Table
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.documents import Document

# --- Logging ---
logger = logging.getLogger(__name__)

# --- RAG Configuration ---
embedding_model = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

# Use a persistent client to save DB to disk
persistent_client = chromadb.PersistentClient(path="./chroma_data")
# We will initialize the Chroma object with the specific collection name inside the functions.

GEMINI_VISION_MODEL = "google/gemini-1.5-flash"

# --- Service Call Functions ---

async def call_gemini_ocr(file_path: str) -> Optional[str]:
    """
    Processes a document (PDF or image) using a multimodal model (Gemini) for high-quality OCR.

    Args:
        file_path: The local path to the document file to process.

    Returns:
        The extracted text content.
    """
    if not OPENROUTER_API_KEY:
        return "[Skipping OCR: OPENROUTER_API_KEY is not set]"

    logger.info(f"Processing {file_path} with Gemini Vision model...")
    
    image_parts = []
    try:
        # Check if the file is a PDF
        if file_path.lower().endswith('.pdf'):
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=200) # Higher DPI for better quality
                img_bytes = pix.tobytes("png")
                base64_image = base64.b64encode(img_bytes).decode('utf-8')
                image_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}})
            doc.close()
        # Otherwise, assume it's an image
        else:
            with open(file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                image_parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})
    except Exception as e:
        logger.error(f"Failed to pre-process file for Gemini: {e}", exc_info=True)
        return f"[Error: Failed to read file {os.path.basename(file_path)}. Details: {e!s}]"

    if not image_parts:
        return "[Error: Could not extract any images from the document to process.]"

    # Add a transport with retries for transient network errors
    transport = httpx.AsyncHTTPTransport(retries=3)
    async with httpx.AsyncClient(timeout=300.0, transport=transport) as client:
        try:
            response = await client.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": GEMINI_VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "You are an expert OCR engine. Transcribe the following document image(s) accurately. Preserve the original formatting, including tables, as much as possible. The document is in Vietnamese."},
                                *image_parts
                            ]
                        }
                    ]
                }
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                logger.error(f"Gemini OCR failed with 503 Service Unavailable: {e}")
                return "[Lỗi: Dịch vụ OCR (Gemini) hiện đang tạm thời không khả dụng. Vui lòng thử lại sau ít phút.]"
            logger.error(f"An HTTP error occurred during Gemini OCR: {e}")
            return f"[Lỗi: Lỗi HTTP ({e.response.status_code}) khi gọi dịch vụ OCR.]"
        except httpx.RequestError as e:
            logger.error(f"An HTTP error occurred during Gemini OCR: {e}")
            return f"[Error: Gemini OCR failed due to a network issue. Details: {e}]"
        except Exception as e:
            logger.error(f"An unexpected error occurred during Gemini OCR: {e}", exc_info=True)
            return f"[Error: Gemini OCR failed. Details: {e!s}]"

async def call_unstructured_partition(file_path: str) -> Optional[str]:
    """
    Processes non-image files like .docx, .pptx using unstructured.io.
    This is a fallback for formats that don't need vision-based OCR.

    Args:
        file_path: The local path to the document file to process.

    Returns:
        The extracted content as a single string. Tables are converted to HTML.
    """
    logger.info(f"Processing {file_path} with unstructured.io (non-OCR)...")
    try:
        def partition_sync():
            # Use basic strategy for text-based files
            elements = partition(filename=file_path)
            output_parts = [str(el) for el in elements if str(el).strip()]
            return "\n\n".join(output_parts)
        return await asyncio.to_thread(partition_sync)
    except Exception as e:
        logger.error(f"An unexpected error occurred during unstructured (non-OCR) partitioning: {e}", exc_info=True)
        return f"[Error: Unstructured failed to process {os.path.basename(file_path)}. Details: {e!s}]"

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
    
    # Add a transport with retries for transient network errors
    transport = httpx.AsyncHTTPTransport(retries=3)
    async with httpx.AsyncClient(timeout=180.0, transport=transport) as client:
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

    # Add a transport with retries for transient network errors
    transport = httpx.AsyncHTTPTransport(retries=3)
    async with httpx.AsyncClient(timeout=180.0, transport=transport) as client:
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

# --- RAG Pipeline Functions ---

def chunk_text(text: str) -> list:
    """Splits the given text into smaller chunks."""
    logger.info(f"Chunking text of length {len(text)}...")
    return text_splitter.split_text(text)

def add_to_vector_store(chunks: list, metadatas: list, collection_name: str):
    """Adds text chunks to a specific collection in the persistent vector store."""
    if not chunks:
        logger.warning("No chunks provided to create vector store.")
        return
    
    if len(chunks) != len(metadatas):
        logger.error("Mismatch between number of chunks and metadatas. Aborting.")
        return
    
    # Initialize Chroma with the specific collection for adding texts
    vector_store_for_add = Chroma(
        client=persistent_client, collection_name=collection_name, embedding_function=embedding_model
    )
    logger.info(f"Adding {len(chunks)} chunks with metadata to collection '{collection_name}'...")
    vector_store_for_add.add_texts(texts=chunks, metadatas=metadatas)

def clear_vector_store(collection_name: str):
    """Clears all documents from a specific user's collection."""
    logger.info(f"Clearing all documents from collection '{collection_name}'...")
    persistent_client.delete_collection(name=collection_name)

def list_collections(user_id: int) -> list[str]:
    """Lists all collections for a given user."""
    all_collections = persistent_client.list_collections()
    user_prefix = f"user_{user_id}_"
    return [c.name for c in all_collections if c.name.startswith(user_prefix)]

def delete_collection(collection_name: str):
    """Deletes a specific collection from the database."""
    logger.info(f"Deleting collection '{collection_name}'...")
    persistent_client.delete_collection(name=collection_name)

async def get_rag_answer(collection_name: str, question: str, chat_history: list, model: str) -> str:
    """
    Gets an answer to a question using the RAG pipeline.
    """
    logger.info(f"Getting RAG answer for question: '{question}'")

    vector_store = Chroma(
        client=persistent_client, collection_name=collection_name, embedding_function=embedding_model
    )
    retriever = vector_store.as_retriever()

    # --- 1. Standalone Question Generation Chain ---
    # This chain condenses the chat history and new question into a single, standalone question.
    standalone_question_prompt = ChatPromptTemplate.from_messages([
        ("system", "Given a chat history and a follow-up question, rephrase the follow-up question to be a standalone question. Answer in the original language of the follow-up question."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])

    # A separate, cheaper model can be used for this simple task.
    # For now, we use the same one.
    standalone_question_chain = standalone_question_prompt | (lambda msg: call_openrouter_summarize(msg.to_string(), model))

    # --- 2. Answer Generation Chain ---
    # This chain takes the standalone question and context to generate the final answer.
    answer_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert assistant. Use the following retrieved context to answer the user's question. If you don't know the answer, just say that you don't know. Answer in Vietnamese.\n\nContext:\n{context}"),
        ("human", "{question}")
    ])

    # 2. Define a function to format the retrieved documents
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs if isinstance(doc, Document))

    # 3. Combine the chains
    async def get_standalone_question(input_dict):
        # Only generate a standalone question if there is a chat history
        if input_dict.get("chat_history"):
            return await standalone_question_chain.ainvoke(input_dict)
        return input_dict["question"]

    full_rag_chain = (
        {
            "context": get_standalone_question | retriever | format_docs,
            "question": get_standalone_question,
        }
        | answer_prompt
        | (lambda msg: call_openrouter_summarize(msg.to_string(), model))
    )

    try:
        # Invoke the full chain with the original question and history
        result = await full_rag_chain.ainvoke({"question": question, "chat_history": chat_history})
        return result
    except Exception as e:
        logger.error(f"Error in RAG chain: {e}", exc_info=True)
        return f"[Error: An error occurred while generating the answer. Details: {e!s}]"