# ─────────────────────────────────────────────────────────────────────────────
# psql-ranking-poc — FastAPI backend
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# System deps (needed for asyncpg / psycopg C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and scripts
COPY app/ ./app/
COPY scripts/ ./scripts/

# Expose the API port
EXPOSE 8001

# ── Default command (dev mode with hot-reload) ─────────────────────────────
# In production, override with:
#   command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
