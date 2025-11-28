"""
Background task scheduler using APScheduler.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler = None


def get_scheduler() -> AsyncIOScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def setup_scheduler() -> AsyncIOScheduler:
    """
    Set up and configure the background task scheduler.

    Returns:
        Configured AsyncIOScheduler instance
    """
    scheduler = get_scheduler()

    # Import task functions here to avoid circular imports
    from src.tasks.data_collector import collect_orchestrator_data

    # Schedule orchestrator data collection
    scheduler.add_job(
        collect_orchestrator_data,
        IntervalTrigger(seconds=settings.orchestrator_poll_interval),
        id="collect_orchestrator_data",
        name="Collect Orchestrator Status",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping runs
    )

    logger.info(
        f"Scheduled orchestrator data collection every {settings.orchestrator_poll_interval} seconds"
    )

    return scheduler


def start_scheduler() -> None:
    """Start the scheduler."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Background scheduler started")


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Background scheduler stopped")
        _scheduler = None
