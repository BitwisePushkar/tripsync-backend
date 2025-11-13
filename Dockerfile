FROM python:3.13-slim AS django

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/main

ENV DJANGO_SETTINGS_MODULE=main.settings

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       netcat-openbsd \
       libpq-dev \
       gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* /app/

WORKDIR /app

RUN uv sync --no-dev --frozen --no-install-project

ENV PATH="/app/.venv/bin:$PATH"

COPY . /app/

WORKDIR /app/main

COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]

FROM nginx:1.27-alpine AS nginx

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80