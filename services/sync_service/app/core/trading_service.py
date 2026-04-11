import httpx
import logging
from .config import settings
from .influx_service import influx_service

logger = logging.getLogger("sync-service")
CORE_SERVICE_URL = settings.CORE_SERVICE_URL


class TradingService:
    """Sensor service for MT5 terminal logic and strategy evaluation."""

    def __init__(self):
        self.last_report = []

    async def relay_signal(
        self, symbol: str, action: str, price: float, strategy: str = "SR_50"
    ):
        """Relays a raw signal to the Core Hub dispatcher."""
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "symbol": symbol,
                    "action": action,
                    "price": price,
                    "strategy": strategy,
                }
                logger.info(
                    f"Relaying {strategy} {action} signal for {symbol} to Core Hub"
                )
                await client.post(
                    f"{CORE_SERVICE_URL}/signals", json=payload, timeout=5.0
                )
            except Exception as e:
                logger.error(f"Failed to relay signal to Core Hub: {e}")

    async def check_signals(self, symbol: str):
        """Unified strategy evaluation and signal relaying."""
        try:
            from ..infra.indicators import PriceActionIndicators as Indicators
            from ..infra.strategy import SRBounceRejection as Strategy
            from ..infra.trading_utils import filter_last_trading_days

            # 1. Over-fetch context for indicators
            df_raw = influx_service.get_resampled_candles(
                symbol, interval="15m", start="-7d"
            )

            # 2. Slice to exactly the last 3 trading days
            df = filter_last_trading_days(df_raw, n_days=3)

            if df is None or df.empty:
                logger.debug(f"No resampled data for {symbol} to check signals.")
                return

            # 2. Add indicators
            df = Indicators.add_dynamic_support_resistance(df, window=50)
            df = Indicators.add_atr(df, period=14)

            # 3. Get current signal
            signal_data = Strategy.get_current_signal(
                df, sup_col="Sup_50", res_col="Res_50", atr_col="ATR_14"
            )

            if signal_data and signal_data.get("action") != "HOLD":
                logger.info(f"Strategy Triggered: {signal_data['action']} for {symbol}")
                await self.relay_signal(
                    symbol=symbol,
                    action=signal_data["action"],
                    price=df["Close"].iloc[-1],
                    strategy=Strategy.strategy_id,
                )

        except Exception as e:
            logger.error(f"Error checking signals for {symbol}: {e}")


trading_service = TradingService()
