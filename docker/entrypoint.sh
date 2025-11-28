#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting Orchestrator API..."
# Use single worker to avoid multiple scheduler instances
exec uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --loop uvloop \
    --http httptools
