FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY api/requirements.txt ./requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY api /app/api

ENV PYTHONPATH=/app

CMD ["sh", "-c", "python -m api.wait_for_db && uvicorn api.app:app --host 0.0.0.0 --port 8000"]
