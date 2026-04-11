from zoneinfo import ZoneInfo
import pandas as pd
from datetime import datetime
from rich.console import Console
from rich.table import Table
from ..core.influx_service import influx_service

console = Console()


class DataHealthMonitor:
    @staticmethod
    def get_precision_forex_index(
        start_dt: datetime, end_dt: datetime
    ) -> pd.DatetimeIndex:
        """Generates the expected per-minute timestamps for the Forex market (Wall Street Time)."""
        full_range = pd.date_range(start=start_dt, end=end_dt, freq="1min", tz="UTC")
        ny_tz = ZoneInfo("US/Eastern")

        # New York Close is always Friday 17:00 NY Time
        # New York Open is Sunday 17:00 NY Time
        expected = []
        for ts in full_range:
            ny_ts = ts.astimezone(ny_tz)
            weekday = ny_ts.weekday()
            hour = ny_ts.hour

            is_weekend = False
            if weekday == 5:
                is_weekend = True  # Sat (Always)
            elif weekday == 4 and hour >= 17:
                is_weekend = True  # Fri Night (Closed after 5 PM)
            elif weekday == 6 and hour < 17:
                is_weekend = True  # Sun morning (Closed before 5 PM)

            if not is_weekend:
                expected.append(ts)

        return pd.DatetimeIndex(expected)

    @classmethod
    def check_integrity(
        cls, symbol: str, days: int = 14, log_table: bool = True
    ) -> dict:
        """
        Scans InfluxDB for gaps and duplicates.
        Returns a dictionary summary and optionally prints a Rich Table.
        """
        symbol = symbol.strip().upper()

        df = influx_service.get_historical_data(symbol, start=f"-{days}d")

        if df.empty:
            return {
                "symbol": symbol,
                "status": "empty",
                "gaps": [],
                "duplicates": 0,
            }

        # --- 1. Intelligent Gap Detection ---
        # Instead of a hardcoded 22:00 UTC filter, we check for gaps
        # within the ACTUAL trading periods found in your DB.
        df = df.sort_index()
        full_range = pd.date_range(
            start=df.index.min(), end=df.index.max(), freq="1min", tz="UTC"
        )

        # Filter matches Sunday 22:00 to Friday 22:00 (Standard)
        # but we only compare against what's within the DB's own boundaries
        expected_index = full_range[
            ((full_range.weekday == 6) & (full_range.hour >= 22))  # Sun Night
            | (full_range.weekday < 4)  # Mon-Thu
            | ((full_range.weekday == 4) & (full_range.hour < 22))  # Fri
        ]

        missing_times = expected_index.difference(df.index)

        # --- 2. Filter out "Edge Gaps" (Start/End of broker uptime) ---
        # A gap is ONLY real if the broker was clearly active before AND after it.
        # If it's at the end of Friday or beginning of Sunday, we ignore it.
        real_missing = []
        for m in missing_times:
            # To be a real gap, we MUST find at least one bar in the DB
            # within 4 hours both BEFORE and AFTER this timestamp.
            has_next = df.index[df.index > m].min()
            has_prev = df.index[df.index < m].max()

            if (
                not pd.isna(has_next)
                and (has_next - m) < pd.Timedelta(hours=4)
                and not pd.isna(has_prev)
                and (m - has_prev) < pd.Timedelta(hours=4)
            ):
                real_missing.append(m)

        missing_times = pd.DatetimeIndex(real_missing)

        gaps = []
        if len(missing_times) > 0:
            current_start = missing_times[0]
            count = 1
            for i in range(1, len(missing_times)):
                if missing_times[i] == missing_times[i - 1] + pd.Timedelta(minutes=1):
                    count += 1
                else:
                    gaps.append(
                        {
                            "start": current_start,
                            "end": missing_times[i - 1],
                            "count": count,
                        }
                    )
                    current_start = missing_times[i]
                    count = 1
            gaps.append(
                {"start": current_start, "end": missing_times[-1], "count": count}
            )

        # --- 2. Duplicate Detection ---
        duplicates_count = int(df.index.duplicated().sum())

        # --- 3. Logging ---
        if log_table and (gaps or duplicates_count > 0):
            table = Table(
                title=f"Data Health: {symbol} (Last {days}d)",
                title_style="bold magenta",
            )
            table.add_column("Type", style="cyan")
            table.add_column("Start (UTC)", style="white")
            table.add_column("End (UTC)", style="white")
            table.add_column("Count", justify="right", style="bold red")

            for g in gaps:
                table.add_row(
                    "GAP",
                    g["start"].strftime("%Y-%m-%d %H:%M"),
                    g["end"].strftime("%Y-%m-%d %H:%M"),
                    str(g["count"]),
                )

            if duplicates_count > 0:
                table.add_row("DUPLICATES", "-", "-", str(duplicates_count))

            console.print(table)

        return {
            "symbol": symbol,
            "status": "ok" if not gaps and duplicates_count == 0 else "issue",
            "total_missing": len(missing_times),
            "total_duplicates": duplicates_count,
            "gaps": gaps,
            "df": df,
        }
