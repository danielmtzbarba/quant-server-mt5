from typing import List
from fastapi import APIRouter, HTTPException
import logging
from ..core.mt5_service import mt5_service
from datetime import datetime

logger = logging.getLogger("mt5-service")

router = APIRouter(prefix="/api", tags=["Monitoring"])


@router.get("/health")
def health_check():
    info = mt5_service.get_terminal_info()
    if info is None:
        return {"status": "unhealthy", "error": "MT5 Unavailable"}
    return {
        "status": "healthy",
        "terminal": info._asdict(),
        "gmt_offset": mt5_service.get_gmt_offset(),
    }


@router.get("/positions")
def get_positions():
    pos = mt5_service.get_positions()
    return [p._asdict() for p in pos] if pos else []


@router.post("/symbols")
def set_symbols(symbols: List[str]):
    mt5_service.tracked_symbols.clear()
    for s in symbols:
        mt5_service.tracked_symbols.add(s.upper())
    logger.info(f"Updated dynamic tracking: {list(mt5_service.tracked_symbols)}")
    return {"status": "success", "tracked": list(mt5_service.tracked_symbols)}


@router.get("/symbols")
def get_symbols():
    return {"tracked": list(mt5_service.tracked_symbols)}


@router.get("/history")
def get_history(symbol: str, count: int = 1000):
    rates = mt5_service.fetch_rates(symbol, count)
    if rates is None:
        raise HTTPException(status_code=404, detail="No rates found")

    gmt_offset = mt5_service.get_gmt_offset()
    candles = []
    for r in rates:
        # Broker Time = UTC + Offset -> UTC = Broker Time - Offset
        ts = datetime.utcfromtimestamp(r["time"] - gmt_offset).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        candles.append(
            {
                "timestamp": ts,
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": int(r["tick_volume"]),
            }
        )
    return {
        "symbol": symbol.upper(),
        "timeframe": "M1",
        "gmt_offset": gmt_offset,
        "candles": candles,
    }
