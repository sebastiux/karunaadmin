# Single-service deploy: build the React frontend, then serve it from FastAPI.
# One container, one URL — no CORS needed. Point your Railway service's
# Root Directory at the repo root (default); Railway auto-detects this file.

# ---- stage 1: build the frontend --------------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Empty API base => the SPA calls /api on its own origin (same service).
ENV VITE_API_URL=""
# Realtime is optional and lives in a separate service; leave it unset here.
ENV VITE_REALTIME_URL=""
RUN npm run build

# ---- stage 2: backend + bundled frontend ------------------------------------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
# Bake the built SPA into the location main.py serves from.
COPY --from=frontend /web/dist ./app/static

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
