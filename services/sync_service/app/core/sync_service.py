import pandas as pd
from datetime import timedelta
from typing import List, Dict, Any
import structlog
from .config import settings
from .influx_service import influx_service
from .mt5_client import mt5_client
from ..infra.health import DataHealthMonitor
from ..infra.indicators import PriceActionIndicators as Indicators
from ..infra.strategy import SRBounceRejection as Strategy

logger = structlog.get_logger(__name__)


class SyncService:
    def __init__(self):
        self.repair_flags: Dict[str, List[Dict[str, Any]]] = {}
        self.latest_signals: Dict[str, Dict[str, Any]] = {}

    async def run_health_check(self, symbol: str, days: int = 14):
        try:
            report = DataHealthMonitor.check_integrity(
                symbol, days=days, log_table=False
            )

            if report["status"] == "empty":
                logger.warning(
                    "database_empty",
                    symbol=symbol,
                    backfill_days=settings.RECOVERY_BACKFILL_DAYS,
                )
                await self.backfill_history(
                    symbol, days=settings.RECOVERY_BACKFILL_DAYS
                )
            elif report["gaps"]:
                logger.warning(
                    "data_gaps_found",
                    symbol=symbol,
                    gap_count=len(report["gaps"]),
                    backfill_days=settings.RECOVERY_BACKFILL_DAYS,
                )
                await self.backfill_history(
                    symbol, days=settings.RECOVERY_BACKFILL_DAYS
                )
            else:
                logger.info("health_check_passed", symbol=symbol)
                self.repair_flags.pop(symbol, None)
            return report
        except Exception as e:
            logger.error("health_check_failed", symbol=symbol, error=str(e))
            return {"status": "error", "message": str(e)}

    def get_sync_status(self, symbol: str):
        symbol = symbol.strip().upper()
        last_time = influx_service.get_last_timestamp(symbol)
        return {"symbol": symbol, "last_timestamp": last_time, "status": "success"}

    def check_repair(self, symbol: str):
        symbol = symbol.strip().upper()
        gaps = self.repair_flags.get(symbol, [])
        formatted_gaps = []
        for g in gaps:
            start = (
                g["start"].strftime("%Y-%m-%dT%H:%M:%S")
                if hasattr(g["start"], "strftime")
                else g["start"]
            )
            end = (
                g["end"].strftime("%Y-%m-%dT%H:%M:%S")
                if hasattr(g["end"], "strftime")
                else g["end"]
            )
            formatted_gaps.append({"start": start, "end": end})
        return {"repair": bool(formatted_gaps), "gaps": formatted_gaps}

    def verify_history(self, symbol: str, gmt_offset: int, candles: List[Dict]):
        if not candles:
            return {"status": "success", "mismatched_bars": 0}
        try:
            df_mt5 = pd.DataFrame(candles)
            df_mt5["timestamp"] = pd.to_datetime(df_mt5["timestamp"]).dt.tz_localize(
                None
            )
            df_mt5["timestamp"] = df_mt5["timestamp"] - pd.to_timedelta(
                gmt_offset, unit="s"
            )
            df_mt5["timestamp"] = df_mt5["timestamp"].dt.tz_localize("UTC")
            df_mt5.set_index("timestamp", inplace=True)

            df_mt5 = df_mt5.rename(
                columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                }
            )[["Open", "High", "Low", "Close", "Volume"]]

            start_time = df_mt5.index.min()
            end_time = df_mt5.index.max()

            df_db = influx_service.get_historical_data(
                symbol,
                start=start_time.isoformat(),
                stop=(end_time + timedelta(seconds=1)).isoformat(),
            )

            if df_db.empty:
                logger.warning(
                    f"Verify: DB is empty for {symbol} in range {start_time}-{end_time}. Uploading..."
                )
                influx_service.write_candles(symbol, df_mt5)
                return {"status": "repaired", "mismatched_bars": len(df_mt5)}

            missing_in_db = df_mt5.index.difference(df_db.index)
            if not missing_in_db.empty:
                logger.info(
                    f"Verify: Found {len(missing_in_db)} missing bars for {symbol}. Repairing..."
                )
                repair_df = df_mt5.loc[missing_in_db]
                influx_service.write_candles(symbol, repair_df)
                return {"status": "repaired", "mismatched_bars": len(missing_in_db)}

            return {"status": "success", "mismatched_bars": 0}
        except Exception as e:
            logger.error(f"Error in verify_history for {symbol}: {e}")
            return {"status": "error", "message": str(e)}

    def evaluate_strategy(self, symbol: str, count: int = 288):
        try:
            df_full = influx_service.get_resampled_candles(
                symbol, interval="15m", start="-7d"
            )
            if df_full is None or df_full.empty:
                return None, {"action": "HOLD", "signal_code": 0}

            df_full = Indicators.add_dynamic_support_resistance(df_full, window=50)
            df_full = Indicators.add_atr(df_full, period=14)
            df = df_full.tail(count).copy()
            df = Strategy.bounce_rejection(
                df, sup_col="Sup_50", res_col="Res_50", atr_col="ATR_14"
            )
            latest_signal = Strategy.get_current_signal(
                df, sup_col="Sup_50", res_col="Res_50", atr_col="ATR_14"
            )
            self.latest_signals[symbol] = latest_signal
            return df, latest_signal
        except Exception as e:
            logger.error(f"Strategy evaluation error for {symbol}: {e}")
            return None, {"action": "HOLD", "error": str(e)}

    async def backfill_history(self, symbol: str, days: int = 7):
        symbol = symbol.upper()
        count = days * 1440
        data = await mt5_client.get_history(symbol, count)
        if not data or "candles" not in data:
            logger.error(f"Failed to fetch history for backfill: {symbol}")
            return False

        candles = data["candles"]
        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df.set_index("timestamp", inplace=True)
        df = df.rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
        df = df[["Open", "High", "Low", "Close", "Volume"]]

        return influx_service.write_candles(symbol, df)


sync_service = SyncService()
