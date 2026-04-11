import pandas as pd


class PriceActionIndicators:
    """
    A library of vectorized technical indicators designed for live trading.
    All methods take a DataFrame and return a new DataFrame with appended columns
    to prevent mutating the original data (Data-Leakage safe).
    """

    @staticmethod
    def add_ema(
        df: pd.DataFrame, period: int = 20, column: str = "Close"
    ) -> pd.DataFrame:
        """
        Calculates the Exponential Moving Average (EMA).
        Useful for determining short-term trend direction and dynamic micro-support.
        """
        df = df.copy()
        df[f"EMA_{period}"] = df[column].ewm(span=period, adjust=False).mean()
        return df

    @staticmethod
    def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        Calculates Average True Range (ATR).
        Crucial for day trading to set dynamic Stop-Losses based on current market volatility.
        """
        df = df.copy()

        # Calculate the three components of True Range
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()

        # True range is the maximum of the three
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # ATR is the rolling mean of TR
        df[f"ATR_{period}"] = tr.rolling(window=period).mean()
        return df

    @staticmethod
    def add_dynamic_support_resistance(
        df: pd.DataFrame, window: int = 20
    ) -> pd.DataFrame:
        """
        Calculates dynamic support and resistance channels (similar to Donchian Channels).
        Uses a trailing window (shift) to ensure no future data leakage during live trading.
        """
        df = df.copy()

        # Resistance is the highest high of the previous N candles
        df[f"Res_{window}"] = df["High"].shift(1).rolling(window=window).max()

        # Support is the lowest low of the previous N candles
        df[f"Sup_{window}"] = df["Low"].shift(1).rolling(window=window).min()

        return df

    @staticmethod
    def add_floor_pivots(df_daily: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates classic Floor Pivot Points (Pivot, R1, S1).
        Requires daily candles (or previous session data) as the input.
        """
        df = df_daily.copy()

        df["Pivot"] = (df["High"] + df["Low"] + df["Close"]) / 3
        df["R1"] = (2 * df["Pivot"]) - df["Low"]
        df["S1"] = (2 * df["Pivot"]) - df["High"]

        return df
