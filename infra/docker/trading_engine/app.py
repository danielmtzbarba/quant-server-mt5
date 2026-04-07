import sys
import os
import asyncio
import httpx
import MetaTrader5 as mt5
from fastapi import FastAPI, HTTPException, Query
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import traceback
from datetime import datetime

# STABILITY FIX: Use SelectorEventLoop on Wine
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"
BACKEND_URL = os.environ.get("BACKEND_URL", "http://100.124.95.126:8002")

TRACKED_SYMBOLS = set()
LAST_CANDLE_TIMES = {}

class TradeRequest(BaseModel):
    action: str
    symbol: str
    volume: float = 0.01
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: str = "MT5-REST-API"
    magic: int = 123456

async def candle_publisher():
    print(f"Starting Candle Publisher Task. BACKEND_URL={BACKEND_URL}")
    while True:
        try:
            if not BACKEND_URL:
                await asyncio.sleep(5)
                continue
                
            # Iterate through dynamically tracked symbols
            for symbol in list(TRACKED_SYMBOLS):
                # Copy the last 2 bars. Index 0 is the last FULLY CLOSED bar. Index 1 is the active forming bar.
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 2)
                if rates is None or len(rates) < 2:
                    continue
                
                last_closed_bar = rates[0]
                bar_time = last_closed_bar['time']
                
                # Initialize tracking
                if symbol not in LAST_CANDLE_TIMES:
                    LAST_CANDLE_TIMES[symbol] = bar_time
                    continue
                
                # If the timestamp of the closed bar shifted forward, a new minute just closed!
                if bar_time > LAST_CANDLE_TIMES[symbol]:
                    LAST_CANDLE_TIMES[symbol] = bar_time
                    
                    ts = datetime.utcfromtimestamp(bar_time).strftime('%Y-%m-%d %H:%M:%S').replace(" ", "T")
                    
                    payload = {
                        "symbol": symbol,
                        "timeframe": "M1",
                        "gmt_offset": 0, # GCP Backend will handle broker timezone logic
                        "candles": [{
                            "timestamp": ts,
                            "open": float(last_closed_bar['open']),
                            "high": float(last_closed_bar['high']),
                            "low": float(last_closed_bar['low']),
                            "close": float(last_closed_bar['close']),
                            "volume": int(last_closed_bar['tick_volume'])
                        }]
                    }
                    
                    async with httpx.AsyncClient() as client:
                        login = os.environ.get("MT5_LOGIN", "0")
                        url = f"{BACKEND_URL}/upload_candles?mt5_login={login}"
                        try:
                            # Fire and forget webhook
                            await client.post(url, json=payload, timeout=5)
                            print(f"[PUSH] Uploaded {symbol} M1 candle: {ts}")
                        except Exception as e:
                            print(f"[ERROR] Failed to push candle to {url}: {e}")
            
            # Poll continuously at high frequency to catch the exact second a M1 bar ticks over
            await asyncio.sleep(1) 
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Exception in candle_publisher loop: {e}")
            await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    login_str = os.environ.get("MT5_LOGIN", "")
    password = os.environ.get("MT5_PASSWORD", "")
    server = os.environ.get("MT5_SERVER", "")
    init_params = {"path": MT5_PATH}
    
    if login_str and password and server:
        init_params.update({"login": int(login_str), "password": password, "server": server})
        
    if not mt5.initialize(**init_params):
        print(f"MT5 INIT FAILED: {mt5.last_error()}")
    else:
        print("MT5 REST API Initialized")
        
    # Start background workers
    publisher_task = asyncio.create_task(candle_publisher())
        
    yield
    publisher_task.cancel()
    mt5.shutdown()

app = FastAPI(title="MT5 Engine Headless REST API", lifespan=lifespan)


# --- MT5 State & Administration Endpoints ---

@app.get("/api/health")
def health_check():
    info = mt5.terminal_info()
    if info is None: return {"status": "unhealthy", "error": mt5.last_error()}
    return {"status": "healthy", "terminal": info._asdict()}

@app.get("/api/positions")
def get_positions():
    """GCP Backend Pulls this. Replaces bi-directional position streaming."""
    pos = mt5.positions_get()
    if pos is None: return []
    return [p._asdict() for p in pos]


# --- Dynamic Symbol Tracking (Replaces sync.mq5 attachment) ---

@app.post("/api/symbols")
def set_symbols(symbols: List[str]):
    """Set the list of symbols to continuously track for M1 candle closures."""
    global TRACKED_SYMBOLS
    TRACKED_SYMBOLS.clear()
    for s in symbols:
        TRACKED_SYMBOLS.add(s.upper())
    return {"status": "success", "tracked": list(TRACKED_SYMBOLS)}

@app.get("/api/symbols")
def get_symbols():
    """Get the currently tracked symbols."""
    return {"tracked": list(TRACKED_SYMBOLS)}

@app.get("/api/history")
def get_history(symbol: str, count: int = 1000):
    """Fetch historical M1 candles directly via REST (replaces verify_history webhook)."""
    rates = mt5.copy_rates_from_pos(symbol.upper(), mt5.TIMEFRAME_M1, 0, count)
    if rates is None:
        raise HTTPException(status_code=404, detail="No rates found or invalid symbol")
        
    candles = []
    for r in rates:
        ts = datetime.utcfromtimestamp(r['time']).strftime('%Y-%m-%d %H:%M:%S').replace(" ", "T")
        candles.append({
            "timestamp": ts,
            "open": float(r['open']),
            "high": float(r['high']),
            "low": float(r['low']),
            "close": float(r['close']),
            "volume": int(r['tick_volume'])
        })
        
    return {
        "symbol": symbol.upper(),
        "timeframe": "M1",
        "gmt_offset": 0,
        "candles": candles
    }


# --- Execution (Replaces client.mq5 /poll mechanism) ---

@app.post("/api/order")
def place_order(trade: TradeRequest):
    try:
        symbol = trade.symbol.upper()
        order_type = mt5.ORDER_TYPE_BUY if trade.action.upper() == 'BUY' else mt5.ORDER_TYPE_SELL
        
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            raise HTTPException(status_code=400, detail=f"No tick data for {symbol}")
            
        price = trade.price or (tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid)
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": trade.volume,
            "type": order_type,
            "price": price,
            "magic": trade.magic,
            "comment": trade.comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        if trade.sl is not None: request["sl"] = trade.sl
        if trade.tp is not None: request["tp"] = trade.tp

        print(f"Sending order: {request}")
        result = mt5.order_send(request)
        
        if result is None:
            last_err = mt5.last_error()
            print(f"CRITICAL: order_send returned None. MT5 Error: {last_err}")
            raise HTTPException(status_code=500, detail=f"MT5 order_send returned None: {last_err}")

        print(f"Order Result: retcode={result.retcode}, comment={result.comment}")
        return {
            "status": "success" if result.retcode == mt5.TRADE_RETCODE_DONE else "failed",
            "retcode": result.retcode,
            "comment": result.comment,
            "ticket": result.order,
            "error_code": mt5.last_error()
        }
    except Exception as e:
        print(f"EXCEPTION in place_order: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
