from pydantic import BaseModel
from typing import Optional, List


class TradeRequest(BaseModel):
    action: str
    symbol: Optional[str] = None
    volume: float = 0.01
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    target: Optional[float] = None
    comment: str = "MT5-REST-API"
    magic: int = 123456
    ticket: Optional[int] = None


class TradeDBCandle(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDataPoint(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: int


class TradeDBPayload(BaseModel):
    symbol: str
    timeframe: str = "M1"
    gmt_offset: int = 0
    candles: List[TradeDBCandle]


class OrderResponse(BaseModel):
    status: str
    retcode: int
    comment: str
    ticket: Optional[int] = None
    error_code: int


class PositionEvent(BaseModel):
    ticket: int
    symbol: str
    type: str  # BUY/SELL
    volume: float
    price: float
    time: str
    status: str  # OPENED, CLOSED


class TradeErrorEvent(BaseModel):
    action: str
    error: str
    code: int
