
import os
import asyncio
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from bs4 import BeautifulSoup
from typing import Optional
from dotenv import load_dotenv
import httpx
from services import call_openrouter_summarize # Already async

# --- Basic Setup ---
load_dotenv()

app = FastAPI()

# --- Environment & Service Configuration ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEFAULT_SUMMARY_MODEL = "anthropic/claude-3.5-sonnet"

# --- Helper Functions ---

async def send_event(event_name: str, data: str):
    """
    Formats a message for Server-Sent Events (SSE).

    Args:
        event_name: The name of the event.
        data: The data to be sent with the event.

    Returns:
        A string formatted for SSE.
    """
    return f"event: {event_name}\ndata: {data}\n\n"

# --- API Endpoints ---

@app.get("/")
def read_root():
    """Returns a simple message to indicate that the server is running."""
    return {"message": "MCP Server is running."}

@app.get("/summarize-url/")
async def summarize_url(url: str = Query(..., description="The URL of the webpage to summarize.")):
    """
    Fetches the content of a URL, summarizes it, and streams the progress using Server-Sent Events (SSE).

    The endpoint performs the following steps:
    1. Fetches the content of the provided URL.
    2. Cleans the HTML to extract the main text content.
    3. Sends the extracted text to the OpenRouter API for summarization.
    4. Streams the progress of these steps to the client using SSE.

    Args:
        url: The URL of the webpage to summarize.

    Returns:
        A StreamingResponse that sends events to the client.
    """
    async def event_generator():
        try:
            # Step 1: Fetching URL
            yield await send_event("message", "Đang tải nội dung từ URL...")
            await asyncio.sleep(1) # Simulate work

            async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0'}, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
            
            # Step 2: Cleaning HTML
            yield await send_event("message", "Đã tải xong, đang làm sạch HTML và tách nội dung...")
            await asyncio.sleep(1)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # Remove script and style elements
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()
            
            text = soup.get_text(separator='\n', strip=True)
            
            if not text:
                yield await send_event("error", "Không tìm thấy nội dung văn bản trên trang web này.")
                return

            # Step 3: Summarizing
            yield await send_event("message", f"Đã tách được {len(text)} ký tự. Đang gửi cho AI để tóm tắt...")
            await asyncio.sleep(1)

            summary = await call_openrouter_summarize(text, DEFAULT_SUMMARY_MODEL)
            
            # Step 4: Complete
            yield await send_event("complete", summary)

        except httpx.RequestError as e:
            yield await send_event("error", f"Lỗi khi tải URL: {e}")
        except Exception as e:
            yield await send_event("error", f"Đã xảy ra lỗi không mong muốn: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
