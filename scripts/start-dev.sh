#!/bin/bash
# Start development environment
# Usage: ./scripts/start-dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Starting development environment..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please review .env and update settings as needed."
fi

# Start all services
docker compose up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 5

# Check health
docker compose ps

echo ""
echo "Development environment started!"
echo "  API:      http://localhost:${API_PORT:-8001}"
echo "  Docs:     http://localhost:${API_PORT:-8001}/docs"
echo "  Postgres: localhost:5432"
echo "  Redis:    localhost:6379"
echo ""
echo "View logs: docker compose logs -f"
echo "Stop:      ./scripts/stop-dev.sh"
