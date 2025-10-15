# Trợ lý Bot Telegram Đa Năng

Dự án này là một bot Telegram được xây dựng bằng Python, có khả năng xử lý tài liệu và âm thanh, tích hợp các mô hình AI mạnh mẽ để cung cấp các tính năng thông minh như trích xuất văn bản, tóm tắt và gỡ băng.

## Tính năng chính

- **Xử lý tài liệu (OCR):**
  - Nhận các tệp `.pdf`, `.docx`, `.pptx`, `.png`, `.jpg` và nhiều định dạng khác.
  - Sử dụng thư viện `unstructured.io` mạnh mẽ để phân tích và trích xuất văn bản, có khả năng nhận diện và giữ nguyên cấu trúc của bảng biểu.
  - Cung cấp tùy chọn xem toàn bộ nội dung hoặc tóm tắt.
- **Tóm tắt văn bản:**
  - Tích hợp với **OpenRouter** để truy cập các mô hình ngôn ngữ lớn (LLM) hàng đầu cho việc tóm tắt.
  - Các mô hình được hỗ trợ: `Claude 3.5 Sonnet`, `Gemini 1.5 Flash`, `GPT-4o Mini`.
  - Người dùng có thể chọn mô hình mình muốn sử dụng.
- **Gỡ băng âm thanh:**
  - Nhận các tệp âm thanh và tin nhắn thoại.
  - Sử dụng mô hình **OpenAI Whisper** để chuyển đổi giọng nói thành văn bản.
- **Giao diện tương tác:**
  - Sử dụng các nút bấm (`InlineKeyboardMarkup`) để hướng dẫn người dùng một cách trực quan.
  - Cập nhật tin nhắn theo thời gian thực để báo cáo tiến trình xử lý.

## Ngôn ngữ và Kiến trúc

- **Ngôn ngữ:** **Python 3**
- **Thư viện chính:**
  - `python-telegram-bot`: Framework để xây dựng bot.
  - `unstructured`: Thư viện phân tích và trích xuất dữ liệu từ tài liệu phức tạp.
  - `httpx`: Thư viện client HTTP bất đồng bộ để gọi API.
  - `python-dotenv`: Để quản lý các biến môi trường.
- **Kiến trúc:**
  - **Event-Driven (Hướng sự kiện):** Bot phản ứng với các hành động của người dùng (gửi tin nhắn, tệp, nhấn nút).
  - **API Integration:** Bot hoạt động như một trung tâm điều phối, gọi đến các API của bên thứ ba để thực hiện các tác vụ cốt lõi:
    - **Telegram API:** Giao tiếp với người dùng.
    - **OpenRouter API:** Dùng cho việc tóm tắt.
    - **OpenAI API:** Dùng cho việc gỡ băng âm thanh.
  - **Asynchronous (Bất đồng bộ):** Tận dụng `asyncio` của Python để xử lý đồng thời nhiều tác vụ (như tải tệp, gọi API) mà không làm block luồng chính, giúp bot luôn phản hồi nhanh chóng.

## Cài đặt và Khởi chạy

1.  **Clone repository (nếu có):**
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

3.  **Tạo tệp `.env`:**
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

5.  **Chạy bot:**
    ```bash
    python main.py
    ```

Bot sẽ bắt đầu chạy và bạn có thể tương tác với nó trên Telegram.
