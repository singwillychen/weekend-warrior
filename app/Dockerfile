# ============================================================
# 週末戰士 FastAPI 後端 — Dockerfile
# 適用：ARM64 (QNAP TS-932PX)
# ============================================================

FROM python:3.11-slim

# 系統依賴（PDF/Word 輸出需要）
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先複製 requirements 以利 Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式碼
COPY . .

# 建立上傳與輸出目錄
RUN mkdir -p uploads exports

# 啟動 FastAPI（uvicorn）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
