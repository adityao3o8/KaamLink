FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
  && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

COPY backend /app/backend
COPY docs_kb /app/docs_kb
COPY eval /app/eval
COPY docs /app/docs

# Build frontend
COPY frontend /app/frontend
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
  && apt-get install -y nodejs \
  && cd /app/frontend && npm install && npm run build \
  && rm -rf /app/frontend/node_modules

ENV PYTHONPATH=/app/backend
ENV DATABASE_URL=sqlite:////app/backend/kaamlink.db
WORKDIR /app/backend

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
