# Sử dụng một image Python nhẹ làm base
FROM python:3.9-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# Cập nhật pip và cài đặt các gói hệ thống cần thiết (nếu có)
# unstructured cần poppler-utils để xử lý PDF.
# tesseract-ocr là một engine OCR mạnh mẽ mà unstructured có thể sử dụng.
# libgl1 là thư viện đồ họa cần thiết cho OpenCV (một dependency của unstructured).
RUN apt-get update && apt-get install -y poppler-utils tesseract-ocr libgl1

# Sao chép file requirements.txt trước để tận dụng cache của Docker
COPY requirements.txt .

# Cài đặt các thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ code của ứng dụng vào thư mục làm việc
COPY . .

# Tạo thư mục downloads để bot có thể lưu file tạm
RUN mkdir -p /app/downloads