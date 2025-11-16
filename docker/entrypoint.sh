#!/bin/bash
set -e

echo "Creating logs directory..."
mkdir -p /app/logs

echo "Waiting for PostgreSQL..."
until nc -z ${POSTGRES_HOST:-db} ${POSTGRES_PORT:-5432}; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "PostgreSQL started"

echo "Collecting static files..."
python manage.py collectstatic --noinput

exec "$@"
