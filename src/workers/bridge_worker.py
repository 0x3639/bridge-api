#!/usr/bin/env python3
"""
Standalone bridge data collector worker.

Run separately from API to ensure complete isolation:
    python -m src.workers.bridge_worker

Or via Docker Compose:
    docker compose up bridge-worker
"""
import asyncio
import logging
import sys

from src.config import settings
from src.workers.bridge_collector import BridgeCollector

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for the bridge worker."""
    logger.info("Starting bridge worker...")
    logger.info(f"Bridge RPC URL: {settings.bridge_rpc_url}")
    logger.info(f"Poll interval: {settings.bridge_poll_interval}s")
    logger.info(f"Batch size: {settings.bridge_batch_size}")

    collector = BridgeCollector()

    try:
        await collector.run()
    except KeyboardInterrupt:
        logger.info("Bridge worker interrupted by user")
    except Exception as e:
        logger.error(f"Bridge worker error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
