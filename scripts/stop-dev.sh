#!/bin/bash
# Stop development environment
# Usage: ./scripts/stop-dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Stopping development environment..."

docker compose down

echo "Development environment stopped."
