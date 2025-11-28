"""
WebSocket service for real-time status broadcasts.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manager for WebSocket connections and broadcasts."""

    def __init__(self):
        # Map user_id -> set of active connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # All connections regardless of user
        self.all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)
        self.all_connections.add(websocket)

        logger.info(f"WebSocket connected for user {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Remove a WebSocket connection."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

        self.all_connections.discard(websocket)

        logger.info(f"WebSocket disconnected for user {user_id}")

    async def broadcast_status(self, status_data: dict) -> None:
        """
        Broadcast status update to all connected clients.

        Args:
            status_data: The status data to broadcast
        """
        message = json.dumps(
            {
                "type": "status_update",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": status_data,
            },
            default=str,
        )

        disconnected = []

        for connection in self.all_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.all_connections.discard(connection)
            # Find and remove from user mapping
            for user_id, connections in list(self.active_connections.items()):
                if connection in connections:
                    connections.discard(connection)
                    if not connections:
                        del self.active_connections[user_id]
                    break

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a message to a specific user's connections."""
        if user_id not in self.active_connections:
            return

        message_str = json.dumps(message, default=str)
        disconnected = []

        for connection in self.active_connections[user_id]:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to send to user {user_id}: {e}")
                disconnected.append(connection)

        for connection in disconnected:
            self.active_connections[user_id].discard(connection)
            self.all_connections.discard(connection)

    @property
    def connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self.all_connections)

    @property
    def user_count(self) -> int:
        """Get number of connected users."""
        return len(self.active_connections)


# Global WebSocket manager instance
_ws_manager: WebSocketManager = None


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
