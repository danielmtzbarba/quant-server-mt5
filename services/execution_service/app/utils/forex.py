from datetime import datetime, timezone

# Defined in UTC per Babypips
FOREX_MARKETS = {
    "Sydney": {"open": 21, "close": 6},
    "Tokyo": {"open": 0, "close": 9},
    "London": {"open": 7, "close": 16},
    "New York": {"open": 13, "close": 22},
}


def is_market_open(market_name: str, hour: int) -> bool:
    """Helper to check if a specific market is open at a given UTC hour."""
    times = FOREX_MARKETS.get(market_name)
    if not times:
        return False

    start, end = times["open"], times["close"]

    # Handle wrap around midnight (e.g., Sydney 21:00 to 06:00)
    if start > end:
        return hour >= start or hour < end
    else:
        return start <= hour < end


def get_active_forex_markets(time_utc: datetime = None) -> list[str]:
    """
    Returns a list of forex markets that are currently open.
    Expects a timezone-aware datetime object in UTC, or assumes current UTC time.
    """
    if time_utc is None:
        time_utc = datetime.now(timezone.utc)

    # Forex market is closed on weekends: Friday 5:00 PM ET to Sunday 5:00 PM ET
    # 5:00 PM ET is exactly 21:00 UTC / 22:00 UTC depending on Daylights savings.
    # To be generic, let's just check if it's Saturday or Sunday UTC.
    weekday = time_utc.weekday()
    if weekday == 5:  # Saturday
        return []

    # Sunday before Sydney open (21:00 UTC) is closed.
    hour = time_utc.hour
    if weekday == 6 and hour < 21:
        return []

    # Friday after New York closes (22:00 UTC) is closed.
    if weekday == 4 and hour >= 22:
        return []

    active_markets = []
    for market in FOREX_MARKETS.keys():
        if is_market_open(market, hour):
            active_markets.append(market)

    return active_markets


def score_trading_hour(time_utc: datetime = None) -> int:
    """
    Scores the given hour from 0 to 10 based on market overlap and volume.
    Higher score indicates better liquidity and tighter spreads.
    - 10: London/New York Overlap (Highest volume)
    - 7: Sydney/Tokyo or Tokyo/London Overlap
    - 4: Single market open
    - 0: Markets closed (Weekends/Holidays)
    """
    active_markets = get_active_forex_markets(time_utc)

    if not active_markets:
        return 0

    if "London" in active_markets and "New York" in active_markets:
        # The Golden overlap: More than 50% of trading volume occurs here
        return 10

    if len(active_markets) >= 2:
        # Other overlaps (Sydney/Tokyo, Tokyo/London)
        return 7

    # Only one session is active
    return 4
