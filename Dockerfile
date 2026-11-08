# One container for the Fly.io deploy: the customer site (web-customer, built in stage 1) served by
# engine_api.py at /, and the API at /api. Fly's remote builder builds this file - no local Docker needed.

# ---- stage 1: build the customer site (it links the menu PDFs in domains/restaurant/docs)
FROM node:20-slim AS web
WORKDIR /build
COPY web-customer/package.json web-customer/package-lock.json web-customer/
RUN cd web-customer && npm ci
COPY web-customer/ web-customer/
COPY domains/restaurant/docs/ domains/restaurant/docs/
RUN cd web-customer && npm run build

# ---- stage 2: Python API
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    MEMORY_BACKEND=persistent \
    SHEETS_ENABLED=false \
    DEBUG_MODE=false
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# F10: download the flashrank re-ranking model at build time so the first question isn't slow
RUN python -c "from flashrank import Ranker; Ranker(model_name='ms-marco-MiniLM-L-12-v2')"

COPY . .
COPY --from=web /build/web-customer/dist web-customer/dist
RUN mkdir -p /data

EXPOSE 8000
CMD ["uvicorn", "engine_api:app", "--host", "0.0.0.0", "--port", "8000"]
