FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/auth


FROM base AS production

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health/', timeout=5)"

CMD ["sh", "-c", "python manage.py migrate && gunicorn auth.wsgi:application --bind 0.0.0.0:8000 --workers 3 & daphne -b 0.0.0.0 -p 8001 auth.asgi:application"]