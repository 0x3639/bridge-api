import logging

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db, get_redis
from src.core.security import hash_token
from src.models.token import ApiToken
from src.models.user import User
from src.services.orchestrator_service import OrchestratorService
from src.services.websocket_service import get_websocket_manager
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


async def validate_ws_token(token: str, db: AsyncSession) -> User | None:
    """Validate a WebSocket authentication token."""
    # Hash the token to look it up
    token_hash = hash_token(token)

    result = await db.execute(
        select(ApiToken)
        .options(joinedload(ApiToken.user))
        .where(
            ApiToken.token_hash == token_hash,
            ApiToken.is_revoked == False,
            or_(
                ApiToken.expires_at == None,
                ApiToken.expires_at > datetime.now(timezone.utc),
            ),
        )
    )
    api_token = result.scalar_one_or_none()

    if api_token is None:
        return None

    if not api_token.user.is_active:
        return None

    # Update last used
    api_token.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return api_token.user


def extract_token_from_subprotocol(websocket: WebSocket) -> str | None:
    """
    Extract token from WebSocket subprotocol header.

    Supports format: "authorization.bearer.TOKEN_VALUE"
    This is more secure than query params as it's not logged by proxies.
    """
    subprotocols = websocket.headers.get("sec-websocket-protocol", "")
    for protocol in subprotocols.split(","):
        protocol = protocol.strip()
        if protocol.startswith("authorization.bearer."):
            return protocol.replace("authorization.bearer.", "")
    return None


@router.websocket("/ws/status")
async def websocket_status(
    websocket: WebSocket,
    token: str | None = Query(None, description="API token for authentication (prefer subprotocol)"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """
    WebSocket endpoint for real-time orchestrator status updates.

    Authentication options (in order of preference):
    1. Subprotocol: Connect with Sec-WebSocket-Protocol: authorization.bearer.YOUR_TOKEN
       This is more secure as the token is not logged in URL by proxies/browsers.
    2. Query param: ws://host/api/v1/ws/status?token=your_api_token
       Still supported for backwards compatibility.

    Messages:
    - Send "ping" to receive "pong" (heartbeat)
    - Receive status_update messages when orchestrator status changes

    Message format:
    {
        "type": "status_update",
        "timestamp": "2024-01-15T10:30:00Z",
        "data": {
            "bridge_status": "online",
            "online_count": 18,
            "total_count": 20,
            "orchestrators": [...]
        }
    }
    """
    # Try subprotocol authentication first (more secure), fall back to query param
    auth_token = extract_token_from_subprotocol(websocket) or token

    if not auth_token:
        await websocket.close(code=4001, reason="No authentication token provided")
        return

    # Validate token
    user = await validate_ws_token(auth_token, db)
    if user is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    manager = get_websocket_manager()
    user_id = str(user.id)

    await manager.connect(websocket, user_id)

    try:
        # Send initial status immediately
        service = OrchestratorService(db, redis)
        current_status = await service.get_current_status()
        await websocket.send_json(
            {
                "type": "initial_status",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": current_status,
            }
        )

        # Keep connection alive and handle messages
        while True:
            try:
                data = await websocket.receive_text()

                # Handle ping/pong
                if data.lower() == "ping":
                    await websocket.send_text("pong")
                else:
                    # Echo back unknown messages
                    await websocket.send_json(
                        {
                            "type": "echo",
                            "message": data,
                        }
                    )

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for user {user_id}")
                break

    finally:
        manager.disconnect(websocket, user_id)
