import asyncio
import httpx
import structlog
import logging
from ..config import settings
from ..mt5_client import mt5_client

logger = structlog.get_logger(__name__)


class PositionMonitor:
    def __init__(self):
        self.active_positions = set()

    async def run(self):
        logger.info(
            "worker_started",
            worker="position_monitor",
            backend_url=settings.BACKEND_URL,
        )

        # Initialize active positions from service
        initial_pos = await mt5_client.get_positions()
        self.active_positions = (
            set(p["ticket"] for p in initial_pos) if initial_pos is not None else set()
        )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Initialized with {len(self.active_positions)} positions.")

        while True:
            try:
                if not settings.BACKEND_URL:
                    await asyncio.sleep(5)
                    continue

                logger.debug("mt5_poll_started")
                pos_list = await mt5_client.get_positions()
                if pos_list is None:
                    logger.warning("mt5_poll_failed", reason="MT5 Service Unavailable")
                    await asyncio.sleep(2)
                    continue

                current_tickets = (
                    set(p["ticket"] for p in pos_list) if pos_list else set()
                )

                # Detect OPENED
                opened = current_tickets - self.active_positions
                for t in opened:
                    p = [pos for pos in pos_list if pos["ticket"] == t][0]
                    payload = {
                        "ticket": t,
                        "status": "OPENED",
                        "symbol": p["symbol"],
                        "type": p["type"],
                        "volume": p["volume"],
                        "price": p["price_open"],
                    }
                    await self._notify_backend("opened", payload)

                # Detect CLOSED
                closed = self.active_positions - current_tickets
                for t in closed:
                    # NOTE: Basic closing info. Detailed profit info would require history poll if needed.
                    payload = {
                        "ticket": t,
                        "status": "CLOSED",
                        "profit": 0.0,
                    }  # Simplified
                    await self._notify_backend("closed", payload)

                self.active_positions = current_tickets
                await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("worker_error", worker="position_monitor", error=str(e))
                await asyncio.sleep(5)

    async def _notify_backend(self, event_type: str, payload: dict):
        """Relays a position event to the Core Hub."""
        async with httpx.AsyncClient() as client:
            # Hub endpoint: core-service/position_event?event_type=...&mt5_login=...
            url = f"{settings.BACKEND_URL}/position_event"
            params = {"event_type": event_type.upper(), "mt5_login": settings.MT5_LOGIN}
            try:
                await client.post(url, params=params, json=payload, timeout=5)
                logger.info(
                    "hub_relay_success",
                    event_type=event_type.upper(),
                    ticket=payload["ticket"],
                )
            except Exception as e:
                logger.error(
                    "hub_relay_failed", event_type=event_type.upper(), error=str(e)
                )


monitor = PositionMonitor()


async def position_monitor_task():
    await monitor.run()
