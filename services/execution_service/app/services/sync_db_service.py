import threading
import time
import pandas as pd
from datetime import timedelta
from typing import List, Dict, Any
from common_logging import setup_logging
from trade_db.api import MarketDataAPI
from utils.health import DataHealthMonitor
from utils.indicators import PriceActionIndicators as Indicators
from utils.strategy import SRBounceRejection as Strategy

logger = setup_logging("execution-service", tag="SYNC", color="blue")


class SyncDBService:
    def __init__(self):
        self.repair_flags: Dict[str, List[Dict[str, str]]] = {}
        self.monitored_symbols = ["EURUSD"]
        self.latest_signals: Dict[str, Dict[str, Any]] = {}

    def start_health_monitor(self):
        """Starts the background health check thread."""
        thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
        thread.start()

    def _health_monitor_loop(self):
        while True:
            for symbol in self.monitored_symbols:
                self.run_health_check(symbol)
            time.sleep(600)  # Every 10 minutes

    def run_health_check(self, symbol: str, days: int = 14):
        try:
            report = DataHealthMonitor.check_integrity(
                symbol, days=days, log_table=False
            )
            if report["status"] == "empty":
                logger.warning(f"🔦 {symbol}: Database EMPTY. Need backfill.")
                self.repair_flags[symbol] = [{"start": "-14d", "end": "now"}]
            elif report["gaps"]:
                logger.warning(f"🔦 {symbol}: {len(report['gaps'])} Gaps Found")
                self.repair_flags[symbol] = report["gaps"]
            else:
                logger.info(f"🔦 {symbol}: Health check passed.")
                self.repair_flags.pop(symbol, None)
        except Exception as e:
            logger.error(f"Health check failed for {symbol}: {e}")

    def get_sync_status(self, symbol: str):
        symbol = symbol.strip().upper()
        with MarketDataAPI() as db:
            last_time = db.get_last_timestamp(symbol)
            return {"symbol": symbol, "last_timestamp": last_time, "status": "success"}

    def check_repair(self, symbol: str):
        symbol = symbol.strip().upper()
        gaps = self.repair_flags.get(symbol, [])

        # Format for MT5 EA (rigid 19-char ISO parsing)
        formatted_gaps = []
        for g in gaps:
            # Handle both string (fallback) and datetime objects
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

    async def log_candle(
        self, symbol: str, timeframe: str, gmt_offset: int, candles: List[Dict]
    ):
        if not candles:
            return {"status": "success", "inserted": 0}

        df = pd.DataFrame(candles)
        df["Open"] = df["open"]
        df["High"] = df["high"]
        df["Low"] = df["low"]
        df["Close"] = df["close"]
        df["Volume"] = df["volume"]

        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
        df["timestamp"] = df["timestamp"] - pd.to_timedelta(gmt_offset, unit="s")
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        df.set_index("timestamp", inplace=True)
        df = df[["Open", "High", "Low", "Close", "Volume"]]

        # Optional: We still write the single candle to InfluxDB on GCP if
        # the GCP instance has its own local DB or wants a secondary log.
        with MarketDataAPI() as db:
            success = db.write_candles(symbol, df)
            if not success:
                logger.error(f"Failed to mirrored candle for {symbol} to InfluxDB.")

            return {"status": "success", "inserted": len(df)}

    def evaluate_strategy(self, symbol: str, count: int = 288):
        """
        Evaluates the strategy on exactly the last N bars.
        Default 288 = 3 days of 15m candles.
        """
        try:
            with MarketDataAPI() as api:
                # 1. Fetch enough raw data for 'Warm-Up' context
                # We fetch 7 days so indicators have history before the N-bar slice.
                df_full = api.get_resampled_candles(symbol, interval="15m", start="-7d")

                if df_full is None or df_full.empty:
                    return None, {"action": "HOLD", "signal_code": 0}

                # 2. Calculate BASE Indicators (SR/ATR) on full context
                # Fixed 50-bar window for SR sensitivity as requested
                df_full = Indicators.add_dynamic_support_resistance(df_full, window=50)
                df_full = Indicators.add_atr(df_full, period=14)

                # 3. Slice to EXACTLY the last N bars for the dashboard
                df = df_full.tail(count).copy()

                # 4. Apply Strategy to the correctly sized slice
                # Strategy uses the fixed Sup_50/Res_50 columns
                df = Strategy.bounce_rejection(
                    df, sup_col="Sup_50", res_col="Res_50", atr_col="ATR_14"
                )

                # Get the summary signal
                latest_signal = Strategy.get_current_signal(
                    df, sup_col="Sup_50", res_col="Res_50", atr_col="ATR_14"
                )
                self.latest_signals[symbol] = latest_signal
                return df, latest_signal
        except Exception as e:
            logger.error(f"Strategy evaluation error for {symbol}: {e}")
            return None, {"action": "HOLD", "error": str(e)}

    def verify_history(self, symbol: str, gmt_offset: int, candles: List[Dict]):
        """
        Compares a chunk of history from MT5 with the database.
        If bars are missing, it uploads them.
        """
        if not candles:
            return {"status": "success", "mismatched_bars": 0}

        try:
            # 1. Prepare MT5 DataFrame
            df_mt5 = pd.DataFrame(candles)
            df_mt5["Open"] = df_mt5["open"]
            df_mt5["High"] = df_mt5["high"]
            df_mt5["Low"] = df_mt5["low"]
            df_mt5["Close"] = df_mt5["close"]
            df_mt5["Volume"] = df_mt5["volume"]

            df_mt5["timestamp"] = pd.to_datetime(df_mt5["timestamp"]).dt.tz_localize(
                None
            )
            df_mt5["timestamp"] = df_mt5["timestamp"] - pd.to_timedelta(
                gmt_offset, unit="s"
            )
            df_mt5["timestamp"] = df_mt5["timestamp"].dt.tz_localize("UTC")
            df_mt5.set_index("timestamp", inplace=True)
            df_mt5 = df_mt5[["Open", "High", "Low", "Close", "Volume"]]

            # 2. Get DB range
            start_time = df_mt5.index.min()
            end_time = df_mt5.index.max()

            with MarketDataAPI() as db:
                # Buffer the end_time by 1s to include the last candle in range
                df_db = db.get_historical_data(
                    symbol,
                    start=start_time.isoformat(),
                    stop=(end_time + timedelta(seconds=1)).isoformat(),
                )

                if df_db.empty:
                    logger.warning(
                        f"Verify: DB is empty for {symbol} in range {start_time} - {end_time}. Uploading whole chunk."
                    )
                    db.write_candles(symbol, df_mt5)
                    return {"status": "repaired", "mismatched_bars": len(df_mt5)}

                # 3. Find gaps (missing timestamps in DB)
                missing_in_db = df_mt5.index.difference(df_db.index)

                if not missing_in_db.empty:
                    logger.info(
                        f"Verify: Found {len(missing_in_db)} missing bars for {symbol}. Repairing..."
                    )
                    repair_df = df_mt5.loc[missing_in_db]
                    db.write_candles(symbol, repair_df)
                    return {"status": "repaired", "mismatched_bars": len(missing_in_db)}

                # 4. Optional: Check for price mismatches (not implemented in original, but good for "Verify")
                # For now, matching indices is the primary "Sync" goal.

                return {"status": "success", "mismatched_bars": 0}

        except Exception as e:
            logger.error(f"Error in verify_history for {symbol}: {e}")
            return {"status": "error", "message": str(e)}


sync_db_service = SyncDBService()
