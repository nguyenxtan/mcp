# Danh sách tính năng

Bot này hỗ trợ các tính năng sau:

## 1. Xử lý tài liệu
- **Trích xuất văn bản:** Hỗ trợ đọc và trích xuất toàn bộ nội dung văn bản từ các file `.pdf`, `.docx`, `.pptx`, `.png`, `.jpg`.
- **Tóm tắt văn bản:** Sau khi trích xuất, người dùng có thể yêu cầu bot tóm tắt nội dung bằng các mô hình ngôn ngữ lớn thông qua OpenRouter.
- **Lựa chọn mô hình:** Người dùng có thể chọn giữa các mô hình khác nhau để tóm tắt (Claude, Gemini, GPT).

## 2. Gỡ băng Audio
- **Xử lý file audio và tin nhắn thoại:** Bot có thể nhận các file audio (ví dụ: `.mp3`, `.ogg`, `.wav`) hoặc các tin nhắn thoại (voice message) được ghi trực tiếp trên Telegram.
- **Gỡ băng:** Sử dụng mô hình `whisper-1` của OpenAI để chuyển đổi giọng nói thành văn bản với độ chính xác cao.

---

## Cách chạy

Dự án này bao gồm hai thành phần chính: một **Telegram Bot** và một **Web Server**. Bạn cần chạy chúng ở hai cửa sổ terminal riêng biệt.

### 1. Chạy Web Server (FastAPI)

Server cung cấp các API cho các dịch vụ xử lý. Để chạy server, sử dụng lệnh:

```bash
/Users/tannx/Documents/mcp-client/mcp-server-python/venv/bin/python server.py
```
Server sẽ chạy tại địa chỉ `http://localhost:8000`.

### 2. Chạy Telegram Bot

Bot là giao diện để người dùng tương tác. Để chạy bot, sử dụng lệnh:

```bash
/Users/tannx/Documents/mcp-client/mcp-server-python/venv/bin/python main.py
```
