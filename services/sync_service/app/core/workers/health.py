import asyncio
import logging
from ..sync_service import sync_service
from ..mt5_client import mt5_client

logger = logging.getLogger("sync-service")


async def health_monitor_loop():
    logger.info("Starting Background Health Monitor (10m interval) in Sync Service.")
    while True:
        try:
            symbols = await mt5_client.get_tracked_symbols()
            for symbol in symbols:
                await sync_service.run_health_check(symbol)
            await asyncio.sleep(600)  # Every 10 minutes
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Exception in health_monitor_loop: {e}")
            await asyncio.sleep(60)
