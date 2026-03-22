# ── Stage 1: Build frontend ──────────────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Production image ─────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install system build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy SAP O2C source data
COPY sap-o2c-data/ ./sap-o2c-data/

# Copy built frontend assets
COPY --from=frontend-build /frontend/dist ./frontend/dist

# Writable data directory for DuckDB + graph cache
RUN mkdir -p ./backend/data

# ── Environment defaults (override via Railway env vars) ──────────────────────
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/sap-o2c-data
ENV DB_PATH=/app/backend/data/o2c.duckdb
ENV GRAPH_CACHE_PATH=/app/backend/data/graph_cache.pkl

EXPOSE 8000

CMD ["sh", "-c", "cd /app/backend && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
