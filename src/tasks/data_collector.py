"""
Background task for collecting orchestrator data.
"""
import logging

from redis.asyncio import Redis

from src.dependencies import async_session_maker, get_redis
from src.services.orchestrator_service import OrchestratorService
from src.services.websocket_service import get_websocket_manager

logger = logging.getLogger(__name__)

# Redis client for background tasks
_bg_redis: Redis = None


async def get_background_redis() -> Redis:
    """Get Redis client for background tasks."""
    global _bg_redis
    if _bg_redis is None:
        from src.config import settings

        _bg_redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _bg_redis


async def collect_orchestrator_data() -> None:
    """
    Collect status from all orchestrators and update the database.

    This function is called periodically by the scheduler.
    """
    logger.info("Starting orchestrator data collection...")

    try:
        # Create a new database session for this task
        async with async_session_maker() as db:
            redis = await get_background_redis()
            service = OrchestratorService(db, redis)

            # Collect data from all orchestrators
            summary = await service.collect_all_status()

            logger.info(
                f"Collection complete: {summary['online']}/{summary['total']} online"
            )

            # Broadcast to WebSocket clients
            ws_manager = get_websocket_manager()
            if ws_manager.connection_count > 0:
                current_status = await service.get_current_status()
                await ws_manager.broadcast_status(current_status)
                logger.info(
                    f"Broadcast status to {ws_manager.connection_count} WebSocket clients"
                )

            await service.close()

    except Exception as e:
        logger.error(f"Error during orchestrator data collection: {e}", exc_info=True)


async def run_initial_collection() -> None:
    """
    Run an initial data collection on startup.

    This ensures we have data available immediately rather than
    waiting for the first scheduled collection.
    """
    logger.info("Running initial orchestrator data collection...")
    await collect_orchestrator_data()
