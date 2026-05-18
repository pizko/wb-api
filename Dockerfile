FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir .

RUN mkdir -p /app/data

CMD ["python", "-m", "api.main", "sync-loop", "--output-dir", "/app/data"]
