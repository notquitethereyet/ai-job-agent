# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps (optional minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Python deps using pip (more reliable for Railway)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . /app

# Environment (Railway provides PORT)
ENV HOST=0.0.0.0

# Run directly with uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host $HOST --port ${PORT:-8000}"]


