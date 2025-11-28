# Orchestrator API

Standalone API service for orchestrator/bridge health monitoring with JWT authentication, rate limiting, and historical data storage.

## Features

- **JWT Authentication**: Long-lived API tokens with secure SHA-256 hashing
- **User Management**: Admin and regular user roles with configurable rate limits
- **Rate Limiting**: Per-user rate limiting using Redis (token bucket algorithm)
- **Real-time Updates**: WebSocket support for live status broadcasts
- **Historical Data**: PostgreSQL storage with indefinite retention
- **Caching**: Redis caching layer for improved performance
- **Docker Deployment**: Full docker-compose setup with production SSL support

## Quick Start (Local Development)

### 1. Clone and Configure

```bash
cd orchestrator-api

# Copy environment template
cp .env.example .env

# Edit .env with your settings
# - Set a secure SECRET_KEY
# - Configure DB_PASSWORD
```

### 2. Start Services

```bash
# Start PostgreSQL, Redis, and the API
docker compose up -d

# View logs
docker compose logs -f api
```

### 3. Create Admin User

```bash
# Using docker exec
docker compose exec api python scripts/create_admin.py

# Or locally (with venv activated)
python scripts/create_admin.py -u admin -e admin@example.com
```

### 4. Seed Orchestrator Nodes

```bash
# From a JSON file (recommended)
docker compose exec api python scripts/seed_nodes.py --json /app/nodes.json

# Or from the original status page mapping file
docker compose exec api python scripts/seed_nodes.py \
  --mapping-file /path/to/orchestrator_mapping.py

# Or from environment variables
docker compose exec api python scripts/seed_nodes.py --from-env
```

#### nodes.json Format

Create a `nodes.json` file with your orchestrator nodes:

```json
[
  {
    "name": "Anvil",
    "ip": "5.161.213.40",
    "pubkey": "Cdq18YwdIT21VcOOl3uczUl/W+RGCqi9CgFIf4CLr8g="
  },
  {
    "name": "Zeno",
    "ip": "51.222.12.113",
    "pubkey": "HxX/6MM7jcjqHAyESWHvLVN3KLWjt6GKgRAgTY9CUqc="
  }
]
```

See `nodes.example.json` for a template.

## Production Deployment

For production deployment with automatic SSL via Caddy:

### 1. Configure Production Environment

```bash
# Copy production environment template
cp .env.prod.example .env.prod

# Edit .env.prod with your settings
nano .env.prod

# Generate secure passwords:
openssl rand -base64 32  # Use for SECRET_KEY
openssl rand -base64 24  # Use for DB_PASSWORD
openssl rand -base64 24  # Use for REDIS_PASSWORD
```

### 2. Configure DNS

Point your domain (e.g., `api.yourdomain.com`) to your server's IP address with an A record.

### 3. Start Production Services

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

Caddy will automatically:
- Obtain SSL certificates from Let's Encrypt
- Redirect HTTP to HTTPS
- Renew certificates before expiry

### 4. Verify

```bash
curl https://api.yourdomain.com/health
```

### Production Architecture

```
Internet → Caddy (ports 80/443, auto SSL) → API (internal only)
                                          → PostgreSQL (internal only)
                                          → Redis (internal only)
```

Only Caddy is exposed to the internet. Database and Redis are isolated on an internal Docker network.

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login with username/password |
| POST | `/api/v1/auth/tokens` | Create API token |
| GET | `/api/v1/auth/tokens` | List your tokens |
| DELETE | `/api/v1/auth/tokens/{id}` | Revoke token |
| GET | `/api/v1/auth/me` | Get current user info |

### User Management (Admin only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users` | List all users |
| POST | `/api/v1/users` | Create user |
| GET | `/api/v1/users/{id}` | Get user |
| PATCH | `/api/v1/users/{id}` | Update user |
| DELETE | `/api/v1/users/{id}` | Deactivate user |

### Orchestrator Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/orchestrators` | List all nodes |
| GET | `/api/v1/orchestrators/status` | Current status (all nodes) |
| GET | `/api/v1/orchestrators/status/summary` | Summary only |
| GET | `/api/v1/orchestrators/{id}` | Node details |
| GET | `/api/v1/orchestrators/{id}/history` | Historical snapshots |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/statistics/bridge` | Bridge health over time |
| GET | `/api/v1/statistics/networks` | Network wrap/unwrap stats |
| GET | `/api/v1/statistics/uptime` | Uptime percentages |

### WebSocket

Connect to `/api/v1/ws/status?token=your_api_token` for real-time updates.

### Health Checks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/ready` | Readiness check (DB, Redis) |

## Authentication

### Using API Tokens

Include your API token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer ora_your_token_here" \
  http://localhost:8000/api/v1/orchestrators/status
```

### Creating Tokens

1. Login to get a session JWT:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "yourpassword"}'
```

2. Use the JWT to create an API token:
```bash
curl -X POST http://localhost:8000/api/v1/auth/tokens \
  -H "Authorization: Bearer <session_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My API Token"}'
```

## Rate Limiting

Rate limits are configured per-user:

| Role | Rate | Burst |
|------|------|-------|
| Admin | 100/s | 200 |
| User | 10/s | 20 |

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Requests per second
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Reset timestamp

## WebSocket Usage

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/status?token=ora_xxx');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Status update:', data);
};

// Send ping to keep alive
setInterval(() => ws.send('ping'), 30000);
```

## Development

### Local Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start dependencies
docker compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

## Configuration

Environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key | (required) |
| `DATABASE_URL` | PostgreSQL connection | (required) |
| `REDIS_URL` | Redis connection | (required) |
| `ORCHESTRATOR_POLL_INTERVAL` | Data collection interval (seconds) | 60 |
| `MIN_ONLINE_FOR_BRIDGE` | Min orchestrators for bridge online | 16 |
| `DEFAULT_RATE_LIMIT_PER_SECOND` | Default user rate limit | 10 |
| `ADMIN_RATE_LIMIT_PER_SECOND` | Admin rate limit | 100 |

## Architecture

```
orchestrator-api/
├── src/
│   ├── api/v1/          # API endpoints
│   ├── core/            # Security, rate limiting
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # Business logic
│   ├── tasks/           # Background jobs
│   └── utils/           # RPC client, helpers
├── alembic/             # Database migrations
├── docker/
│   ├── Dockerfile       # API container
│   └── caddy/           # Caddy reverse proxy config
├── scripts/             # Admin scripts
├── docker-compose.yml       # Local development
└── docker-compose.prod.yml  # Production with Caddy + SSL
```

## Deployment Comparison

| | Local Development | Production |
|---|---|---|
| Command | `docker compose up` | `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d` |
| API Access | `http://localhost:8000` | `https://yourdomain.com` |
| SSL | None | Automatic (Let's Encrypt via Caddy) |
| DB Port | Exposed (5432) | Internal only |
| Redis Port | Exposed (6379) | Internal only |
| Redis Auth | None | Password required |

## License

MIT
