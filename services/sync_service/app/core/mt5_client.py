import httpx
import asyncio
import structlog
from .config import settings
from typing import Optional
from .metrics import LAST_HEARTBEAT, POLLING_LATENCY

logger = structlog.get_logger(__name__)


class MT5Client:
    def __init__(self):
        self.base_url = settings.MT5_SERVICE_URL
        self._client: Optional[httpx.AsyncClient] = None

    async def wait_until_ready(self, timeout: int = 60):
        logger.info("waiting_for_mt5_service", url=self.base_url)
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            health = await self.get_health()
            if health.get("status") == "healthy":
                logger.info("mt5_service_ready")
                return True
            await asyncio.sleep(2)
        logger.error("mt5_service_timeout", timeout=timeout)
        return False

    def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def get_health(self):
        try:
            with POLLING_LATENCY.labels(call_type="health").time():
                client = self.get_client()
                response = await client.get(f"{self.base_url}/api/health")
                data = response.json()
                if data.get("status") == "healthy":
                    LAST_HEARTBEAT.set_to_current_time()  # Use timestamp Gauge
                return data
        except Exception as e:
            logger.error("mt5_health_check_failed", error=str(e))
            return {"status": "unhealthy", "error": str(e)}

    async def get_positions(self):
        try:
            with POLLING_LATENCY.labels(call_type="positions").time():
                client = self.get_client()
                response = await client.get(f"{self.base_url}/api/positions")
                return response.json()
        except Exception as e:
            logger.error("mt5_fetch_positions_failed", error=str(e))
            return None

    async def get_history(self, symbol: str, count: int = 1000):
        try:
            with POLLING_LATENCY.labels(call_type="history").time():
                client = self.get_client()
                params = {"symbol": symbol, "count": count}
                response = await client.get(
                    f"{self.base_url}/api/history", params=params
                )
                if response.status_code == 200:
                    return response.json()
                return None
        except Exception as e:
            logger.error("mt5_fetch_history_failed", symbol=symbol, error=str(e))
            return None

    async def place_order(self, trade_data: dict):
        try:
            with POLLING_LATENCY.labels(call_type="order").time():
                client = self.get_client()
                response = await client.post(
                    f"{self.base_url}/api/order", json=trade_data
                )
                return response.json()
        except Exception as e:
            logger.error("mt5_place_order_failed", error=str(e))
            return {"status": "failed", "comment": str(e)}

    async def get_tracked_symbols(self):
        try:
            with POLLING_LATENCY.labels(call_type="symbols").time():
                client = self.get_client()
                response = await client.get(f"{self.base_url}/api/symbols")
                return response.json().get("tracked", [])
        except Exception as e:
            logger.error("mt5_fetch_symbols_failed", error=str(e))
            return ["EURUSD", "NVDA"]  # Fallback


mt5_client = MT5Client()
