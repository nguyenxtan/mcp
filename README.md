# Trợ lý Bot Telegram Đa Năng

Dự án này là một bot Telegram được xây dựng bằng Python, có khả năng xử lý tài liệu và âm thanh, tích hợp các mô hình AI mạnh mẽ để cung cấp các tính năng thông minh như trích xuất văn bản, tóm tắt và gỡ băng.

## Tính năng chính

- **Xử lý tài liệu nâng cao:**
  - Nhận các tệp `.pdf`, `.docx`, `.pptx`, `.png`, `.jpg` và nhiều định dạng khác.
  - Sử dụng thư viện `unstructured.io` mạnh mẽ để phân tích và trích xuất văn bản, có khả năng nhận diện và giữ nguyên cấu trúc của bảng biểu.

- **Trò chuyện với tài liệu (RAG - Retrieval-Augmented Generation):**
  - Sau khi xử lý tài liệu, bot xây dựng một cơ sở tri thức (vector database) từ nội dung.
  - Người dùng có thể đặt câu hỏi và nhận câu trả lời dựa trên chính nội dung của tài liệu đã tải lên.
  - Hỗ trợ hội thoại nối tiếp, cho phép người dùng hỏi các câu hỏi làm rõ dựa trên câu trả lời trước đó.

- **Gỡ băng âm thanh:**
  - Nhận các tệp âm thanh và tin nhắn thoại.
  - Sử dụng mô hình **OpenAI Whisper** để chuyển đổi giọng nói thành văn bản.

- **Lựa chọn mô hình AI:**
  - Người dùng có thể chọn giữa các mô hình ngôn ngữ lớn (LLM) khác nhau (Claude, Gemini, GPT) để tạo ra câu trả lời.

## Ngôn ngữ và Kiến trúc

- **Ngôn ngữ:** **Python 3**
- **Thư viện chính:**
  - `python-telegram-bot`: Framework để xây dựng bot.
  - `langchain`: Framework điều phối chính cho kiến trúc RAG.
  - `unstructured`: Để phân tích và trích xuất dữ liệu từ tài liệu.
  - `chromadb` & `sentence-transformers`: Để xây dựng cơ sở dữ liệu vector.
  - `httpx`: Thư viện client HTTP bất đồng bộ để gọi API.
  - `python-dotenv`: Để quản lý các biến môi trường.
- **Kiến trúc:**
  - **RAG (Retrieval-Augmented Generation):** Đây là kiến trúc cốt lõi mới.
    1.  **Trích xuất (Extract):** Dùng `unstructured` để đọc nội dung từ file.
    2.  **Chia nhỏ (Chunk):** Dùng `langchain` để chia văn bản thành các "mẩu kiến thức" nhỏ.
    3.  **Vector hóa (Embed):** Dùng `sentence-transformers` để biến mỗi mẩu kiến thức thành một vector.
    4.  **Lưu trữ (Store):** Lưu các vector vào `ChromaDB`.
    5.  **Truy vấn (Retrieve):** Khi người dùng hỏi, tìm kiếm các vector liên quan nhất trong `ChromaDB`.
    6.  **Tạo sinh (Generate):** Gửi các thông tin đã truy vấn được kèm theo câu hỏi đến một LLM (qua OpenRouter) để tạo ra câu trả lời cuối cùng.

## Cài đặt và Khởi chạy

### 1. Cài đặt các công cụ hệ thống

Thư viện `unstructured` cần một số công cụ bên ngoài để xử lý file PDF và hình ảnh (OCR). Bạn cần cài đặt chúng vào hệ điều hành của mình.
- **Trên macOS:** `brew install poppler tesseract`
- **Trên Debian/Ubuntu (cho server):** `apt-get install poppler-utils tesseract-ocr`

### 2. Cài đặt môi trường Python

1.  **Clone repository:**
    ```bash
    git clone <your-repo-url>
    cd mcp-server-python
    ```

2.  **Tạo môi trường ảo và cài đặt thư viện:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Tạo tệp biến môi trường `.env`:**
    Tạo một tệp có tên `.env` trong thư mục gốc của dự án và thêm các API key của bạn vào đó:
    ```env
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"
    OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
    ```

4.  **Tạo thư mục `downloads`:**
    Bot cần một thư mục để lưu trữ tạm thời các tệp tải về.
    ```bash
    mkdir downloads
    ```

5.  **Chạy Bot:**
    ```bash
    python main.py
    ```

Bot sẽ bắt đầu chạy và bạn có thể tương tác với nó trên Telegram.
