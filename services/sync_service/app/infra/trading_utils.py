import pandas as pd
from common_logging import setup_logging

logger = setup_logging("sync-service-utils")


def filter_last_trading_days(df: pd.DataFrame, n_days: int = 3) -> pd.DataFrame:
    """
    Slices a DataFrame (with DatetimeIndex) to exactly the last N calendar days
    that actually contain data points. This gracefully handles weekends and market holidays.

    Args:
        df (pd.DataFrame): The input market data (expecting UTC index).
        n_days (int): Number of trading sessions to display.

    Returns:
        pd.DataFrame: Sliced DataFrame starting from the beginning of the Nth most recent session.
    """
    if df is None or df.empty:
        return df

    # 1. Identify all unique calendar dates in the data
    # (Using .date() ensures we group by full days regardless of time)
    all_dates = pd.Series(df.index.date).unique()
    all_dates.sort()

    if len(all_dates) <= n_days:
        # We already have less than or equal to the requested days
        return df

    # 2. Identify the Nth most recent date
    target_start_date = all_dates[-n_days]
    logger.debug(
        f"Slicing chart to start at {target_start_date} ({len(all_dates)} days available)"
    )

    # 3. Slice the DataFrame
    # Note: We slice from the absolute start (midnight) of that target date
    start_ts = pd.Timestamp(target_start_date).tz_localize(df.index.tz)
    return df[df.index >= start_ts]
