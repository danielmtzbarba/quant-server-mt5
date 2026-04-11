import httpx
import asyncio
import logging
from .config import settings
from typing import Optional

logger = logging.getLogger("sync-service")


class MT5Client:
    def __init__(self):
        self.base_url = settings.MT5_SERVICE_URL
        self._client: Optional[httpx.AsyncClient] = None

    async def wait_until_ready(self, timeout: int = 60):
        logger.info(f"Waiting for MT5 Service to be ready at {self.base_url}...")
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            health = await self.get_health()
            if health.get("status") == "healthy":
                logger.info("MT5 Service is ready.")
                return True
            await asyncio.sleep(2)
        logger.error("Timeout waiting for MT5 Service to be ready.")
        return False

    def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def get_health(self):
        try:
            client = self.get_client()
            response = await client.get(f"{self.base_url}/api/health")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get MT5 health: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def get_positions(self):
        try:
            client = self.get_client()
            response = await client.get(f"{self.base_url}/api/positions")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get MT5 positions: {e}")
            return None

    async def get_history(self, symbol: str, count: int = 1000):
        try:
            client = self.get_client()
            params = {"symbol": symbol, "count": count}
            response = await client.get(f"{self.base_url}/api/history", params=params)
            if response.status_code == 200:
                # Return the full JSON (symbol, timeframe, candles, gmt_offset)
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get MT5 history for {symbol}: {e}")
            return None

    async def place_order(self, trade_data: dict):
        try:
            client = self.get_client()
            response = await client.post(f"{self.base_url}/api/order", json=trade_data)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return {"status": "failed", "comment": str(e)}

    async def get_tracked_symbols(self):
        try:
            client = self.get_client()
            response = await client.get(f"{self.base_url}/api/symbols")
            return response.json().get("tracked", [])
        except Exception as e:
            logger.error(f"Failed to get tracked symbols: {e}")
            return ["EURUSD", "NVDA"]  # Fallback


mt5_client = MT5Client()
