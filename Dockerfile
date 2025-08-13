# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

# System deps (optional minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv 
RUN uv sync --frozen --no-dev

# App code
COPY . /app

# Environment (Railway provides PORT)
ENV HOST=0.0.0.0

# Run using uv run to activate the virtual environment
CMD ["sh", "-c", "uv run uvicorn app.main:app --host $HOST --port ${PORT:-8000}"]


