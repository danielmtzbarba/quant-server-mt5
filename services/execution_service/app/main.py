from fastapi import FastAPI, Request, HTTPException, Query
import uvicorn
import logging
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import os
from typing import List
from pydantic import BaseModel

from services.trading_service import trading_service
from services.sync_db_service import sync_db_service
from common_logging import setup_logging
from common_events import TradingSignal, PositionEvent, TradeErrorEvent
from utils.visualization import MarketVisualizer

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Execution Service...")
    # Definitive runtime silence for Uvicorn logs
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi"]:
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = False
        uv_logger.setLevel(logging.WARNING)

    # Automatically provision the linked MT5 Tailscale backend to stream symbols
    import httpx
    import asyncio
    MT5_ENGINE_URL = os.environ.get("MT5_ENGINE_URL", "http://100.119.34.104:8000")
    
    async def configure_tracking():
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{MT5_ENGINE_URL}/api/symbols", json=["EURUSD", "NVDA"], timeout=5.0)
                logger.info("Successfully registered tracking symbols with MT5 Engine.")
        except Exception as e:
            logger.error(f"Failed to reach MT5 Engine to set tracking symbols on Boot. Retrying later. {e}")
    
    asyncio.create_task(configure_tracking())
    
    yield
    logger.info("Shutting down Execution Service...")


logger = setup_logging("execution-service", tag="TRADING", color="green")

app = FastAPI(title="Execution Service", lifespan=lifespan)

# Setup templates and static files (Point to root templates)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Root templates is 3 levels up from execution_service/app/
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "../../../templates"))

# Start background health monitor
sync_db_service.start_health_monitor()


@app.get("/health")
async def health_check():
    logger.debug("GET /health")
    return {"status": "healthy"}



@app.post("/report")
async def receive_report(request: Request, mt5_login: str = Query(...)):
    """Endpoint for MT5 EA to send full position/account reports."""
    payload = await request.json()
    logger.info(
        f"POST /report from {mt5_login}: {len(payload.get('positions', []))} positions"
    )
    await trading_service.handle_report(mt5_login, payload.get("positions", []))
    return {"status": "success"}


@app.get("/mt5/report/latest")
async def get_latest_report():
    """Retrieve the last received position report from MT5."""
    return {"positions": trading_service.last_report}


@app.post("/signal")
async def receive_signal(signal: TradingSignal):
    """Endpoint for external signals to be broadcasted."""
    logger.info(f"POST /signal: {signal.action} {signal.symbol}")
    success, reason = await trading_service.broadcast_signal(signal)
    if not success:
        if reason == "MAX_POSITIONS_REACHED":
            raise HTTPException(
                status_code=429, detail="Maximum position limit reached. Trade gated."
            )
        raise HTTPException(status_code=500, detail=reason)
    return {"status": "success", "detail": reason}


@app.post("/close_position")
async def close_position(ticket: int):
    """Endpoint for agent to close a specific position via native MT5 push."""
    logger.info(f"POST /close_position: Direct API Dispatch for Ticket {ticket}")
    import httpx
    import os
    MT5_ENGINE_URL = os.environ.get("MT5_ENGINE_URL", "http://100.119.34.104:8000")
    
    async with httpx.AsyncClient() as client:
        try:
            trade_resp = await client.post(
                f"{MT5_ENGINE_URL}/api/order", 
                json={"action": "CLOSE", "ticket": ticket, "symbol": "DUMMY"}, # Symbol is now optional on MT5
                timeout=10.0
            )
            if trade_resp.status_code == 200:
                logger.info(f"MT5 Successfully reversed Ticket {ticket}")
            else:
                logger.error(f"MT5 rejection on CLOSE: {trade_resp.text}")
        except Exception as mt5_err:
            logger.error(f"Network error trying to explicitly close {ticket}: {mt5_err}")
            
    return {"status": "success"}


@app.post("/position_event")
async def position_event(event: PositionEvent, mt5_login: str = Query(...)):
    """General endpoint for position lifecycle events."""
    logger.info(f"POST /position_event [{mt5_login}]: {event.status} {event.ticket}")
    if event.status == "OPENED":
        await trading_service.handle_position_opened(mt5_login, event)
    elif event.status == "CLOSED":
        await trading_service.handle_position_closed(mt5_login, event)
    return {"status": "success"}


@app.post("/position_opened")
async def position_opened(event: PositionEvent, mt5_login: str = Query(...)):
    """Dedicated endpoint for MT5 EA 'OPENED' notification."""
    logger.info(
        f"POST /position_opened [{mt5_login}]: Ticket {event.ticket} {event.symbol}"
    )
    await trading_service.handle_position_opened(mt5_login, event)
    return {"status": "success"}


@app.post("/position_closed")
async def position_closed(event: PositionEvent, mt5_login: str = Query(...)):
    """Dedicated endpoint for MT5 EA 'CLOSED' notification."""
    logger.info(
        f"POST /position_closed [{mt5_login}]: Ticket {event.ticket} Profit: {event.profit}"
    )
    await trading_service.handle_position_closed(mt5_login, event)
    return {"status": "success"}


@app.post("/trade_error")
async def trade_error(event: TradeErrorEvent, mt5_login: str = Query(...)):
    """Endpoint for MT5 EA to report execution failures."""
    logger.error(
        f"POST /trade_error [{mt5_login}]: {event.action} {event.symbol} -> {event.message} ({event.retcode})"
    )
    await trading_service.handle_trade_error(mt5_login, event)
    return {"status": "success"}


# --- SyncDB Endpoints ---


class TradeDBCandle(BaseModel):
    timestamp: str
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


@app.get("/sync_status")
async def get_sync_status(symbol: str = Query(...)):
    logger.info(f"GET /sync_status: {symbol}")
    return sync_db_service.get_sync_status(symbol)


@app.get("/check_repair")
async def check_repair(symbol: str = Query(...)):
    logger.info(f"GET /check_repair: {symbol}")
    return sync_db_service.check_repair(symbol)


@app.post("/upload_candles")
async def upload_candles(payload: TradeDBPayload):
    logger.info(
        f"POST /upload_candles: {payload.symbol} ({len(payload.candles)} candles)"
    )
    result = await sync_db_service.upload_candles(
        payload.symbol,
        payload.timeframe,
        payload.gmt_offset,
        [c.model_dump() for c in payload.candles],
    )
    if result.get("status") == "success":
        # Trigger strategy check
        await trading_service.check_signals(payload.symbol)
    return result


@app.post("/verify_history")
async def verify_history(payload: TradeDBPayload):
    logger.info(f"POST /verify_history: {payload.symbol}")
    return sync_db_service.verify_history(
        payload.symbol, payload.gmt_offset, [c.model_dump() for c in payload.candles]
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, symbol: str = "EURUSD", count: int = 288):
    logger.info(f"GET /dashboard: {symbol} (count={count} bars)")
    df, latest_signal = sync_db_service.evaluate_strategy(symbol, count=count)

    if df is None or df.empty:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "symbol": symbol,
                "total_bars": 0,
                "last_price": "N/A",
                "last_sync": "N/A",
                "chart_html": "<h4>No data found in InfluxDB for this symbol/range.</h4>",
                "latest_signal": {"action": "HOLD", "signal_code": 0},
            },
        )

    # Visualization
    highlights = MarketVisualizer.get_standard_highlights(df)
    fig = MarketVisualizer.get_figure(
        df=df,
        symbol=f"{symbol} (15M) Analysis",
        chart_type="candle",
        overlays=["Sup_50", "Res_50"],
        show_volume=True,
        highlights=highlights,
    )
    chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "symbol": symbol,
            "total_bars": len(df),
            "last_price": f"{df['Close'].iloc[-1]:.5f}",
            "last_sync": df.index[-1].strftime("%Y-%m-%d %H:%M"),
            "chart_html": chart_html,
            "latest_signal": latest_signal,
        },
    )


if __name__ == "__main__":
    logger.info("Execution Service Ready on port 8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)
