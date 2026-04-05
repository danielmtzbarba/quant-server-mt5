import os
from typing import Optional
import pandas as pd
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from common_logging import setup_logging

# Configure logging for the library using rich
logger = setup_logging("execution-service", tag="SYNC", color="blue")


class MarketDataAPI:
    """
    A professional interface for interacting with the InfluxDB market data store.
    Handles connection pooling, query construction, and DataFrame formatting.
    """

    def __init__(self, env_path: str = ".env"):
        """Initializes the database connection using environment variables."""
        load_dotenv(env_path)

        self.url = os.getenv("INFLUX_URL")
        self.token = os.getenv("INFLUX_TOKEN")
        self.org = os.getenv("INFLUX_ORG")
        self.bucket = os.getenv("INFLUX_BUCKET", "massive_history")

        if not all([self.url, self.token, self.org, self.bucket]):
            raise ValueError("Missing critical InfluxDB environment variables.")

        # Initialize the client with a 30s timeout for large historical queries
        self.client = InfluxDBClient(
            url=self.url, token=self.token, org=self.org, timeout=30_000
        )
        self.query_api = self.client.query_api()
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

    def get_historical_data(
        self, symbol: str, start: str, stop: str = "now()"
    ) -> pd.DataFrame:
        """
        Retrieves historical OHLCV data for a specific symbol and time range.

        Args:
            symbol (str): The market ticker (e.g., 'EURUSD').
            start (str): Start time in ISO format (e.g., '2026-01-15T00:00:00Z') or relative (e.g., '-30d').
            stop (str): Stop time in ISO format or relative. Defaults to 'now()'.

        Returns:
            pd.DataFrame: A formatted Pandas DataFrame with DatetimeIndex and OHLCV columns.
        """
        logger.debug(f"DB: Fetching {symbol} ({start})")

        flux_query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {start}, stop: {stop})
          |> filter(fn: (r) => r["_measurement"] == "m1_candles")
          |> filter(fn: (r) => r["Symbol"] == "{symbol}")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> drop(columns: ["_start", "_stop", "_measurement", "Symbol"])
        '''

        try:
            df = self.query_api.query_data_frame(flux_query)

            if isinstance(df, list):
                if not df:
                    return pd.DataFrame()
                df = pd.concat(df)

            if df.empty:
                return df

            # Clean up the InfluxDB metadata columns and format the index
            df = df.drop(columns=["result", "table"], errors="ignore")
            df.rename(columns={"_time": "Time"}, inplace=True)
            df.set_index("Time", inplace=True)
            df.index = pd.to_datetime(df.index)

            # Ensure standard column order
            columns_present = [
                col
                for col in ["Open", "High", "Low", "Close", "Volume"]
                if col in df.columns
            ]
            return df[columns_present]

        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            return pd.DataFrame()

    def get_last_timestamp(self, symbol: str) -> Optional[str]:
        """
        Retrieves the most recent timestamp recorded for a given symbol.
        Uses a optimized query to handle large datasets efficiently.
        """
        symbol = symbol.strip()
        flux_query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -100y)
          |> filter(fn: (r) => r["_measurement"] == "m1_candles")
          |> filter(fn: (r) => r["Symbol"] == "{symbol}")
          |> filter(fn: (r) => r["_field"] == "Close")
          |> last()
        '''
        try:
            result = self.query_api.query(flux_query)
            if not result or not result[0].records:
                return None

            # Use .get_time() to extract the _time column, NOT the price value
            latest_time = result[0].records[0].get_time()

            if hasattr(latest_time, "isoformat"):
                return latest_time.isoformat()
            return str(latest_time)
        except Exception as e:
            logger.error(f"Error fetching last timestamp for {symbol}: {e}")
            return None

    def write_candles(self, symbol: str, df: pd.DataFrame) -> bool:
        """
        Writes a Pandas DataFrame of OHLCV data into InfluxDB.
        Expects a DataFrame with a DatetimeIndex and 'Open', 'High', 'Low', 'Close', 'Volume' columns.
        """
        if df.empty:
            return True

        try:
            points = []
            for timestamp, row in df.iterrows():
                try:
                    open_price = float(row["Open"])
                    high_price = float(row["High"])
                    low_price = float(row["Low"])
                    close_price = float(row["Close"])
                    volume = int(row["Volume"]) if "Volume" in row else 0

                    p = (
                        Point("m1_candles")
                        .tag("Symbol", symbol)
                        .field("Open", open_price)
                        .field("High", high_price)
                        .field("Low", low_price)
                        .field("Close", close_price)
                        .field("Volume", volume)
                        .time(timestamp)
                    )
                    points.append(p)
                except Exception as e:
                    logger.warning(f"Skipping malformed row at {timestamp}: {e}")

            if points:
                self.write_api.write(bucket=self.bucket, org=self.org, record=points)
                logger.debug(
                    f"Successfully wrote {len(points)} candle(s) for {symbol}."
                )

            return True
        except Exception as e:
            logger.error(f"Failed to write candles for {symbol}: {e}")
            return False

    def check_data_integrity(self, symbol: str, start: str, stop: str) -> dict:
        """
        Validates a specific time range for a symbol to check row counts and duplicates.

        Args:
            symbol (str): The market ticker.
            start (str): Start time in ISO format.
            stop (str): Stop time in ISO format.

        Returns:
            dict: A summary of the integrity check.
        """
        df = self.get_historical_data(symbol, start, stop)

        if df.empty:
            logger.warning(f"No data found for {symbol} in the specified range.")
            return {"total_rows": 0, "duplicates": 0}

        # The index is our 'Time' column due to the formatting in get_historical_data
        dupes = df[df.index.duplicated(keep=False)]

        result = {"total_rows": len(df), "duplicates": len(dupes)}

        logger.info(
            f"Integrity Check - Rows: {result['total_rows']} | Duplicates: {result['duplicates']}"
        )
        return result

    def get_resampled_candles(
        self, symbol: str, interval: str, start: str, stop: str = "now()"
    ) -> pd.DataFrame:
        """
        Retrieves historical data aggregated into larger timeframes (e.g., '5m', '1h', '1d').
        Executes OHLCV resampling math directly within the InfluxDB engine.

        Args:
            symbol (str): The market ticker (e.g., 'EURUSD').
            interval (str): The Flux duration literal (e.g., '5m', '15m', '1h', '4h', '1d').
            start (str): Start time in ISO format or relative (e.g., '-30d').
            stop (str): Stop time in ISO format or relative. Defaults to 'now()'.

        Returns:
            pd.DataFrame: A formatted Pandas DataFrame with the resampled OHLCV data.
        """
        logger.debug(f"DB: Resampling {symbol} {interval} ({start})")

        # We split the data by field, apply the correct mathematical aggregation,
        # and then union them back together before pivoting into a clean table.
        flux_query = f'''
        data = from(bucket: "{self.bucket}")
          |> range(start: {start}, stop: {stop})
          |> filter(fn: (r) => r["_measurement"] == "m1_candles")
          |> filter(fn: (r) => r["Symbol"] == "{symbol}")

        o = data |> filter(fn: (r) => r["_field"] == "Open") |> aggregateWindow(every: {interval}, fn: first, createEmpty: false)
        h = data |> filter(fn: (r) => r["_field"] == "High") |> aggregateWindow(every: {interval}, fn: max, createEmpty: false)
        l = data |> filter(fn: (r) => r["_field"] == "Low") |> aggregateWindow(every: {interval}, fn: min, createEmpty: false)
        c = data |> filter(fn: (r) => r["_field"] == "Close") |> aggregateWindow(every: {interval}, fn: last, createEmpty: false)
        v = data |> filter(fn: (r) => r["_field"] == "Volume") |> aggregateWindow(every: {interval}, fn: sum, createEmpty: false)

        union(tables: [o, h, l, c, v])
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> drop(columns: ["_start", "_stop", "_measurement", "Symbol"])
        '''

        try:
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=UserWarning)
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

            columns_present = [
                col
                for col in ["Open", "High", "Low", "Close", "Volume"]
                if col in df.columns
            ]
            return df[columns_present]

        except Exception as e:
            logger.error(f"Failed to fetch resampled data: {e}")
            return pd.DataFrame()

    def close(self):
        """Closes the InfluxDB client connection safely."""
        self.client.close()

    def __enter__(self):
        """Allows use of the API with context managers (the 'with' statement)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensures the connection closes automatically when exiting a 'with' block."""
        self.close()
