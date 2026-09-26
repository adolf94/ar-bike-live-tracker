FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends gcc git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Self-hosted extras live in requirements-selfhost.txt (fastapi, sqlalchemy, ...)
COPY requirements-selfhost.txt .
RUN pip install -r requirements.txt -r requirements-selfhost.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "selfhost.app:app", "--host", "0.0.0.0", "--port", "8000"]
