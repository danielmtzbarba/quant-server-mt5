from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from ..models.schemas import MarketDataPoint
from .config import settings
import logging
import pandas as pd
from typing import Optional
from datetime import datetime

logger = logging.getLogger("sync-service")


class InfluxService:
    def __init__(self):
        self._client: Optional[InfluxDBClient] = None
        self.query_api = None
        self.write_api = None

    def connect(self):
        if not settings.INFLUX_TOKEN:
            logger.warning("INFLUX_TOKEN not set. InfluxDB logic will be disabled.")
            return

        try:
            self._client = InfluxDBClient(
                url=settings.INFLUX_URL,
                token=settings.INFLUX_TOKEN,
                org=settings.INFLUX_ORG,
                timeout=30_000,
            )
            self.query_api = self._client.query_api()
            self.write_api = self._client.write_api(write_options=SYNCHRONOUS)
            logger.info(f"Connected to InfluxDB at {settings.INFLUX_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")

    def write_point(self, symbol: str, data: dict, timestamp: datetime):
        if not self.write_api:
            return
        try:
            point = Point("market_data").tag("symbol", symbol)
            # Enforce types using Pydantic MarketDataPoint
            validated_data = MarketDataPoint(**data).model_dump()
            for k, v in validated_data.items():
                point.field(k, v)
            point.time(timestamp)
            self.write_api.write(bucket=settings.INFLUX_BUCKET, record=point)
        except Exception as e:
            logger.error(f"Failed to write point to InfluxDB: {e}")

    def write_candles(self, symbol: str, df: pd.DataFrame):
        if not self.write_api or df.empty:
            return
        try:
            points = []
            for ts, row in df.iterrows():
                p = Point("market_data").tag("symbol", symbol)
                # Enforce types using Pydantic MarketDataPoint
                try:
                    # Lowercase keys to match Pydantic model fields (open, close, etc.)
                    row_dict = {k.lower(): v for k, v in row.to_dict().items()}
                    p_data = MarketDataPoint(**row_dict).model_dump()
                    for k, v in p_data.items():
                        p.field(k, v)
                except Exception as e:
                    logger.warning(
                        f"Skipping row for {symbol} due to validation error: {e}"
                    )
                    continue
                p.time(ts)
                points.append(p)

            # Batch write
            chunk_size = 1000
            for i in range(0, len(points), chunk_size):
                self.write_api.write(
                    bucket=settings.INFLUX_BUCKET, record=points[i : i + chunk_size]
                )
            return True
        except Exception as e:
            logger.error(f"Failed to write candles to InfluxDB: {e}")
            return False

    def get_historical_data(
        self, symbol: str, start: str, stop: str = "now()"
    ) -> pd.DataFrame:
        if not self.query_api:
            return pd.DataFrame()

        flux_query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: {start}, stop: {stop})
          |> filter(fn: (r) => r["_measurement"] == "market_data")
          |> filter(fn: (r) => r["symbol"] == "{symbol}")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> drop(columns: ["_start", "_stop", "_measurement", "symbol"])
        """
        try:
            df = self.query_api.query_data_frame(flux_query)
            if isinstance(df, list):
                if not df:
                    return pd.DataFrame()
                df = pd.concat(df)
            if df.empty:
                return df

            df = df.drop(columns=["result", "table"], errors="ignore")
            df.rename(columns={"_time": "Time"}, inplace=True)
            df.set_index("Time", inplace=True)
            df.index = pd.to_datetime(df.index)
            # Ensure columns are uppercase for compatibility with strategy utils
            df.columns = [
                c.capitalize() if c.lower() != "volume" else "Volume"
                for c in df.columns
            ]
            return df
        except Exception as e:
            logger.error(f"Failed to fetch data from InfluxDB: {e}")
            return pd.DataFrame()

    def get_last_timestamp(self, symbol: str) -> Optional[str]:
        if not self.query_api:
            return None
        flux_query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: -100y)
          |> filter(fn: (r) => r["_measurement"] == "market_data")
          |> filter(fn: (r) => r["symbol"] == "{symbol}")
          |> filter(fn: (r) => r["_field"] == "close")
          |> last()
        """
        try:
            result = self.query_api.query(flux_query)
            if not result or not result[0].records:
                return None
            latest_time = result[0].records[0].get_time()
            return (
                latest_time.isoformat()
                if hasattr(latest_time, "isoformat")
                else str(latest_time)
            )
        except Exception as e:
            logger.error(f"Error fetching last timestamp for {symbol}: {e}")
            return None

    def get_resampled_candles(
        self, symbol: str, interval: str, start: str, stop: str = "now()"
    ) -> pd.DataFrame:
        if not self.query_api:
            return pd.DataFrame()

        flux_query = f"""
        data = from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: {start}, stop: {stop})
          |> filter(fn: (r) => r["_measurement"] == "market_data")
          |> filter(fn: (r) => r["symbol"] == "{symbol}")

        o = data |> filter(fn: (r) => r["_field"] == "open") |> aggregateWindow(every: {interval}, fn: first, createEmpty: false)
        h = data |> filter(fn: (r) => r["_field"] == "high") |> aggregateWindow(every: {interval}, fn: max, createEmpty: false)
        l = data |> filter(fn: (r) => r["_field"] == "low") |> aggregateWindow(every: {interval}, fn: min, createEmpty: false)
        c = data |> filter(fn: (r) => r["_field"] == "close") |> aggregateWindow(every: {interval}, fn: last, createEmpty: false)
        v = data |> filter(fn: (r) => r["_field"] == "volume") |> aggregateWindow(every: {interval}, fn: sum, createEmpty: false)

        union(tables: [o, h, l, c, v])
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> drop(columns: ["_start", "_stop", "_measurement", "symbol"])
        """
        try:
            df = self.query_api.query_data_frame(flux_query)
            if isinstance(df, list):
                if not df:
                    return pd.DataFrame()
                df = pd.concat(df)
            if df.empty:
                return df

            df = df.drop(columns=["result", "table"], errors="ignore")
            df.rename(columns={"_time": "Time"}, inplace=True)
            df.set_index("Time", inplace=True)
            df.index = pd.to_datetime(df.index)
            df.columns = [
                c.capitalize() if c.lower() != "volume" else "Volume"
                for c in df.columns
            ]
            return df
        except Exception as e:
            logger.error(f"Failed to fetch resampled data: {e}")
            return pd.DataFrame()

    def close(self):
        if self._client:
            self._client.close()


influx_service = InfluxService()
