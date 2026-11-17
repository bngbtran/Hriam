# Backend Hriăm trên Hugging Face Space (CPU Basic, miễn phí). Hugging Face tự build file này, không cần Docker trên máy.
# Nội dung Space do scripts/deploy_hf.py tải lên: Dockerfile, README.md, backend/, scripts/translate.py.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/tmp/hf-cache

# Hugging Face chạy container bằng user có uid 1000
RUN useradd -m -u 1000 user
WORKDIR /app

COPY backend/requirements.txt backend/requirements-ml.txt backend/
RUN pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r backend/requirements.txt -r backend/requirements-ml.txt

COPY --chown=user backend backend
COPY --chown=user scripts/translate.py scripts/translate.py
RUN mkdir -p /app/models /app/backend/storage && chown -R user /app

USER user
WORKDIR /app/backend

# Biến bí mật (Settings → Variables and secrets của Space): DATABASE_URL, SECRET_KEY, PHONE_HMAC_KEY, HF_TOKEN.
# Biến thường: HF_MODEL_REPO, CORS_ORIGINS. Xem docs/DEPLOY.md.
ENV HRIAM_ENV=production \
    MODELS_DIR=/app/models \
    STORAGE_DIR=/app/backend/storage \
    TRUST_PROXY=true \
    COOKIE_SECURE=true \
    MT_PRELOAD=true \
    MT_BEAMS=2

EXPOSE 7860
# Tạo/cập nhật bảng và vai trò (chạy lại nhiều lần vẫn an toàn), rồi mở API. Mô hình tải ở nền khi khởi động.
CMD ["sh", "-c", "python -m app.cli migrate && python -m app.cli seed && uvicorn app.main:app --host 0.0.0.0 --port 7860 --proxy-headers --forwarded-allow-ips='*'"]
