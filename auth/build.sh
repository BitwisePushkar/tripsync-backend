#!/usr/bin/env bash
set -o errexit

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Resetting database tables..."
python reset_database.py

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Faking initial migration..."
python manage.py migrate account zero --fake 2>/dev/null || echo "No existing migrations to remove"

echo "Running migrations..."
python manage.py migrate --fake-initial

echo "Build completed successfully!"