import asyncio
import httpx
import structlog
from datetime import datetime
from ..config import settings
from ..mt5_client import mt5_client
from ..influx_service import influx_service
from ..trading_service import trading_service

logger = structlog.get_logger(__name__)


class CandlePublisher:
    def __init__(self):
        self.last_candle_times = {}

    async def run(self):
        logger.info(
            "worker_started",
            worker="candle_publisher",
            mt5_url=settings.MT5_SERVICE_URL,
        )
        while True:
            try:
                symbols = await mt5_client.get_tracked_symbols()
                for symbol in symbols:
                    data = await mt5_client.get_history(symbol, count=2)
                    if data is None:
                        await asyncio.sleep(2)
                        continue
                    if not data or "candles" not in data or not data["candles"]:
                        continue

                    gmt_offset = data.get("gmt_offset", 0)

                    # The mt5_service returns rates sorted by time.
                    # Last closed bar is at index 0 (if copy_rates_from_pos(0, 2) was used)
                    # Wait, our mt5_service API currently returns them in original order.
                    # Monitoring API history returns them in a list.
                    candles = data["candles"]
                    if len(candles) < 2:
                        continue

                    last_closed_bar = candles[0]
                    bar_time_str = last_closed_bar["timestamp"]

                    if symbol not in self.last_candle_times:
                        self.last_candle_times[symbol] = bar_time_str
                        continue

                    if bar_time_str != self.last_candle_times[symbol]:
                        self.last_candle_times[symbol] = bar_time_str
                        logger.info(
                            f"New candle detected for {symbol} at {bar_time_str}"
                        )

                        # 1. Write to InfluxDB
                        # Use UTC-aware datetime to ensure InfluxDB records it correctly
                        from datetime import timezone

                        ts_utc = datetime.fromisoformat(bar_time_str).replace(
                            tzinfo=timezone.utc
                        )

                        influx_service.write_point(
                            symbol,
                            {
                                "open": last_closed_bar["open"],
                                "high": last_closed_bar["high"],
                                "low": last_closed_bar["low"],
                                "close": last_closed_bar["close"],
                                "volume": last_closed_bar["volume"],
                            },
                            ts_utc,
                        )

                        # 2. Notify Backend
                        if settings.BACKEND_URL:
                            async with httpx.AsyncClient() as client:
                                url = f"{settings.BACKEND_URL}/signal?mt5_login={settings.MT5_LOGIN}"
                                payload = {
                                    "symbol": symbol,
                                    "timeframe": "M1",
                                    "gmt_offset": gmt_offset,
                                    "candles": [last_closed_bar],
                                }
                                try:
                                    await client.post(url, json=payload, timeout=5)
                                    logger.info(
                                        f"Signal notification pushed for {symbol}"
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to notify backend: {e}")

                        # 3. Trigger Strategy Analysis (Consolidated)
                        await trading_service.check_signals(symbol)

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Exception in candle_publisher: {e}")
                await asyncio.sleep(5)


publisher = CandlePublisher()


async def candle_publisher_task():
    await publisher.run()
