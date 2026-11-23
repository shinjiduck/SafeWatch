# Dockerfile để deploy lên Render (hoặc bất kỳ nền tảng nào chạy Docker) —
# tự kiểm soát hệ thống/Python version, tránh lặp lại vòng dò lỗi đã gặp
# trên Streamlit Cloud (Python version sai, thiếu libgl1...).

FROM python:3.12-slim

# libgl1 + libglib2.0-0: opencv-python-headless và mediapipe (qua
# matplotlib nội bộ) vẫn cần 2 thư viện hệ thống này để import được, dù
# app không hiện GUI gì — xem lịch sử git để biết lỗi gốc
# ("ImportError: libGL.so.1").
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# Render (và nhiều nền tảng khác) cấp cổng qua biến môi trường $PORT thay
# vì cố định 8501 — dùng shell form (không phải mảng) để biến môi trường
# được thay thế đúng lúc container khởi động.
CMD streamlit run main.py --server.port=${PORT:-8501} --server.address=0.0.0.0
