FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by docling + psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libxcb1 \
        libx11-6 \
        libxrender1 \
        libxext6 \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY api/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY api /app/api

ENV PYTHONPATH=/app

CMD ["sh", "-c", "python -m api.wait_for_db && uvicorn api.app:app --host 0.0.0.0 --port 8000"]
