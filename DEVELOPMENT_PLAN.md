# Kế Hoạch Phát Triển: Nâng Cấp Bot thành Trợ lý RAG

Đây là lộ trình chi tiết để biến bot Telegram hiện tại thành một hệ thống Hỏi-Đáp (Q&A) dựa trên kiến trúc RAG.

## Giai đoạn 1: Xây dựng đường ống RAG (RAG Pipeline)

### Task 1.1: Cập nhật thư viện

-   Thêm các thư viện cần thiết vào file `requirements.txt`:
    -   `langchain`: Framework điều phối chính.
    -   `sentence-transformers`: Dùng để tạo vector embeddings local.
    -   `chromadb`: Cơ sở dữ liệu vector, chạy trực tiếp trên server.
    -   `beautifulsoup4`: (Nếu cần) để xử lý các bảng HTML từ `unstructured`.

### Task 1.2: Cải tổ `services.py` để tích hợp RAG

-   **Tạo hàm `chunk_text`:** Chia văn bản đầu vào (`full_text`) thành các đoạn nhỏ (chunks) bằng `RecursiveCharacterTextSplitter` của LangChain.
-   **Tạo hàm `create_vector_store`:**
    -   Nhận đầu vào là các `chunks`.
    -   Sử dụng `SentenceTransformerEmbeddings` (ví dụ: model `all-MiniLM-L6-v2`) để chuyển các chunks thành vector.
    -   Lưu các vector này vào `Chroma` và trả về một đối tượng `retriever`.
-   **Tạo hàm `get_rag_answer`:**
    -   Nhận đầu vào là `retriever`, câu hỏi (`question`), và lịch sử hội thoại (`chat_history`).
    -   Dùng `retriever` để tìm các chunks liên quan nhất đến câu hỏi.
    -   **Thiết kế Prompt Nâng cao:** Tạo một prompt template nhận vào: `context` (từ các chunks), `question`, và `chat_history` để LLM có thể trả lời câu hỏi nối tiếp.
    -   Gọi API LLM (qua `call_openrouter_summarize` hoặc một hàm mới) với prompt đã được điền đầy đủ thông tin.

### Task 1.3: Cập nhật luồng xử lý chính trong `main.py`

-   Sửa đổi hàm `_process_file`:
    -   Sau khi dùng `call_unstructured_partition` để lấy `full_text`, hãy gọi các hàm mới trong `services.py` để: chunk_text -> create\_vector\_store.
    -   Lưu đối tượng `retriever` vào `context.user_data['rag_retriever']`.
    -   Khởi tạo `context.user_data['chat_history'] = []`.

## Giai đoạn 2: Cải thiện trải nghiệm người dùng

### Task 2.1: Cập nhật giao diện và luồng hội thoại

-   Trong `main.py`, thay thế hoặc bổ sung nút "Tóm tắt" bằng nút **"❓ Trò chuyện với tài liệu"** (`callback_data='chat_with_doc'`).
-   Khi người dùng nhấn nút này, bot sẽ phản hồi: "✅ Sẵn sàng! Mời bạn đặt câu hỏi về tài liệu này." và chuyển sang trạng thái chờ câu hỏi.
-   Sửa hàm `handle_text_message` để nhận diện trạng thái này:
    -   Khi nhận được câu hỏi, bot sẽ gọi hàm `get_rag_answer` từ `services.py`.
    -   Lưu câu hỏi của người dùng và câu trả lời của bot vào `context.user_data['chat_history']`.
    -   Hiển thị câu trả lời và hỏi lại: "Bạn có muốn hỏi gì thêm không?" để duy trì cuộc hội thoại.

### Task 2.2: Xử lý trạng thái và kết thúc hội thoại

-   Thêm nút "Kết thúc trò chuyện" (`callback_data='end_chat'`) vào các câu trả lời.
-   Khi người dùng nhấn nút này hoặc gửi lệnh `/cancel`, bot sẽ xóa `rag_retriever` và `chat_history` khỏi `context.user_data` và quay về trạng thái ban đầu.