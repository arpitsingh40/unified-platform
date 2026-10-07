FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npx vite build

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends build-essential gcc g++ && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --timeout=120 -r requirements.txt

# Backend source
COPY backend/ .

# Composio catalog — placed in both locations for code path compatibility
COPY memory/composio_catalog.json /app/composio_catalog.json
RUN mkdir -p /app/memory && cp /app/composio_catalog.json /app/memory/composio_catalog.json

# Frontend SPA build
COPY --from=frontend-builder /app/frontend/build /frontend/build

EXPOSE 8000

# Gunicorn with 2 Uvicorn workers for concurrent request handling
# Bumps throughput from 1 req at a time to 2 parallel requests
# For >1000 users, bump to -w 4 and increase Railway RAM to 2GB
CMD gunicorn -w 2 -k uvicorn.workers.UvicornWorker server:app --bind 0.0.0.0:${PORT:-8000} --timeout 120 --graceful-timeout 30
