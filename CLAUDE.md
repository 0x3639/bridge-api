# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Orchestrator API** (Bridge API) - A standalone FastAPI service for orchestrator/bridge health monitoring with JWT authentication, rate limiting, and historical data storage. Currently running in production at `bridgeapi.zenon.info`.

## Tech Stack

- **Framework:** FastAPI (async)
- **Database:** PostgreSQL with asyncpg driver, SQLAlchemy ORM
- **Cache/Rate Limiting:** Redis
- **Authentication:** JWT tokens (session) + API tokens (long-lived, `ora_` prefix)
- **Migrations:** Alembic
- **Testing:** pytest + testcontainers (auto-spin PostgreSQL/Redis containers)
- **Deployment:** Docker Compose with Caddy for automatic SSL

## Common Commands

```bash
# Run tests (requires Docker running for testcontainers)
pytest tests/ -v

# Run specific test file
pytest tests/test_auth.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Start/stop development environment
./scripts/start-dev.sh
./scripts/stop-dev.sh

# Start/stop production environment
./scripts/start-prod.sh
./scripts/stop-prod.sh

# Force rebuild in production (after code changes)
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Create admin user
docker compose exec api python scripts/create_admin.py

# Seed orchestrator nodes
docker compose exec api python scripts/seed_nodes.py --json /app/nodes.json
```

## Architecture

```
src/
├── api/v1/           # API endpoints (auth, users, orchestrators, statistics, websocket)
├── core/             # Security (JWT, password hashing), rate limiting, exceptions
├── models/           # SQLAlchemy models (User, APIToken, OrchestratorNode, etc.)
├── schemas/          # Pydantic request/response schemas
├── services/         # Business logic (orchestrator_service, cache_service, websocket_service)
├── tasks/            # Background jobs (data_collector polls orchestrator nodes)
├── utils/            # RPC client for orchestrator communication
├── config.py         # Environment-based configuration
├── dependencies.py   # FastAPI dependency injection (DB sessions, Redis, auth)
└── main.py           # App entry point, middleware, lifespan
tests/                # Test suite using testcontainers
scripts/              # Admin utilities (create_admin.py, seed_nodes.py, ws_client.py)
```

## Key API Endpoints

- `POST /api/v1/auth/login` - Login, returns JWT
- `POST /api/v1/auth/tokens` - Create API token
- `GET /api/v1/orchestrators/status` - Current status of all nodes
- `GET /api/v1/statistics/uptime` - Uptime percentages
- `WS /api/v1/ws/status?token=xxx` - Real-time status WebSocket

## Environment Variables

Key configuration (see `.env.example` for full list):
- `SECRET_KEY` - JWT signing key (required)
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `ORCHESTRATOR_POLL_INTERVAL` - Data collection interval (default: 60s)
- `MIN_ONLINE_FOR_BRIDGE` - Minimum orchestrators for bridge online (default: 16)

### Security Configuration
- `CORS_ORIGINS` - Allowed CORS origins (comma-separated or "*")
- `HSTS_ENABLED` - Enable HTTP Strict Transport Security (default: false)
- `LOGIN_RATE_LIMIT_PER_MINUTE` - Login attempts per IP per minute (default: 10)

### Database Pool Configuration
- `DB_POOL_SIZE` - Number of permanent connections (default: 5)
- `DB_MAX_OVERFLOW` - Additional connections under load (default: 10)
- `DB_POOL_RECYCLE` - Recycle connections after seconds (default: 3600)

## Testing Notes

- Tests use `testcontainers` - Docker must be running
- Test fixtures in `tests/conftest.py` create isolated DB/Redis per test session
- 49 tests covering auth, users, orchestrators, health, and security
- Tests use the same port (8001) as development

## Important Considerations

- **Production System:** Changes must be backwards compatible
- **Rate Limiting:** Per-user via Redis token bucket (configurable per user)
- **Login Rate Limiting:** IP-based rate limiting to prevent brute force attacks
- **Caching:** Redis caching layer with configurable TTLs
- **WebSocket:** Real-time updates broadcast to authenticated clients (supports subprotocol auth)
- **Background Tasks:** `data_collector.py` polls orchestrator nodes every 60s
- **Security Headers:** HSTS, CSP, X-Frame-Options (configurable)
- **Health Endpoint:** Returns random message from `messages.json`
