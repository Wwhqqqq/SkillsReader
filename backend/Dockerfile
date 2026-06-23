FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/backend/
COPY backend/app /app/backend/app
COPY config /app/config

WORKDIR /app/backend
RUN pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/backend
ENV TZ=Asia/Shanghai

WORKDIR /app
COPY .env.example /app/.env

CMD ["python", "-m", "app.main"]
