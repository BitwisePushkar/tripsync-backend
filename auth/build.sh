#!/usr/bin/env bash
set -o errexit

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Resetting database..."
PGPASSWORD="${DATABASE_URL#*:*:*@*:*/}" psql "${DATABASE_URL}" < reset_db.sql || true

echo "Running migrations..."
python manage.py migrate

echo "Build completed successfully!"