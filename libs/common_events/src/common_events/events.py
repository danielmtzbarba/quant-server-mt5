from pydantic import BaseModel
from typing import Optional


class Candle(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: float


class TradingSignal(BaseModel):
    symbol: str
    action: str
    candle: Optional[Candle] = None
    timestamp: Optional[str] = None
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None


class ExecutionRequest(BaseModel):
    action: str  # BUY, SELL, CLOSE
    symbol: str
    volume: float
    price: Optional[float] = None
    ticket: Optional[int] = None


class PositionEvent(BaseModel):
    ticket: int
    symbol: Optional[str] = None
    volume: Optional[float] = None
    price: Optional[float] = None
    type: Optional[int] = None  # 0=Buy, 1=Sell
    profit: Optional[float] = 0.0
    status: str  # OPENED, CLOSED
