#!/bin/bash
# Stop production environment
# Usage: ./scripts/stop-prod.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Stopping production environment..."

docker compose -f docker-compose.prod.yml --env-file .env.prod down

echo "Production environment stopped."
