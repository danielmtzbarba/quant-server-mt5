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
from common_events import TradingSignal, PositionEvent
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


@app.get("/poll")
async def poll_commands(mt5_login: str = Query(...)):
    """Endpoint for MT5 EA to poll for pending commands."""
    logger.debug(f"GET /poll for {mt5_login}")
    command = trading_service.get_next_mt5_command(mt5_login)
    if command:
        return JSONResponse(content=command)
    return JSONResponse(content={"action": "NONE"})


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
    """Endpoint for agent to close a specific position."""
    logger.info(f"POST /close_position: Ticket {ticket}")
    trading_service.queue_mt5_command("CLOSE", ticket=ticket)
    return {"status": "success"}


@app.post("/refresh_mt5")
async def refresh_mt5():
    """Endpoint for agent to force a data refresh from MT5."""
    logger.info("POST /refresh_mt5")
    trading_service.queue_mt5_command("REPORT")
    return {"status": "success"}


@app.get("/commands")
async def get_commands():
    """Endpoint for agent to verify pending MT5 commands."""
    logger.info("GET /commands")
    from execution_queue.queue import mt5_queue

    return {"pending": mt5_queue.get_all_pending()}


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
