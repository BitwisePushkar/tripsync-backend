#!/bin/sh

set -e

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
until nc -z "${DB_HOST}" "${DB_PORT}"; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
until nc -z "${REDIS_HOST}" "${REDIS_PORT}"; do
  sleep 1
done
echo "Redis is ready."

echo "Waiting for RabbitMQ at ${RABBITMQ_HOST}:${RABBITMQ_PORT:-5672}..."
until nc -z "${RABBITMQ_HOST}" "${RABBITMQ_PORT:-5672}"; do
  sleep 1
done
echo "RabbitMQ is ready."

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Starting uvicorn..."
exec uvicorn main.asgi:application \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info