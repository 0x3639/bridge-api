#!/bin/bash
# Start production environment
# Usage: ./scripts/start-prod.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Starting production environment..."

# Check if .env.prod exists
if [ ! -f .env.prod ]; then
    echo "Error: .env.prod file not found!"
    echo "Please copy .env.prod.example to .env.prod and configure it."
    exit 1
fi

# Verify required variables are set
source .env.prod
if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "change-this-to-a-secure-random-string" ]; then
    echo "Error: SECRET_KEY must be set in .env.prod"
    exit 1
fi

if [ -z "$DB_PASSWORD" ]; then
    echo "Error: DB_PASSWORD must be set in .env.prod"
    exit 1
fi

if [ -z "$REDIS_PASSWORD" ]; then
    echo "Error: REDIS_PASSWORD must be set in .env.prod"
    exit 1
fi

if [ -z "$DOMAIN" ]; then
    echo "Error: DOMAIN must be set in .env.prod"
    exit 1
fi

# Start all services
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check health
docker compose -f docker-compose.prod.yml --env-file .env.prod ps

echo ""
echo "Production environment started!"
echo "  API: https://${DOMAIN}"
echo ""
echo "View logs: docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f"
echo "Stop:      ./scripts/stop-prod.sh"
