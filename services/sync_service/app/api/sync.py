from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from ..core.sync_service import sync_service
from ..core.trading_service import trading_service
from ..core.mt5_client import mt5_client
from ..models.schemas import (
    TradeDBPayload,
    TradeRequest,
    PositionEvent,
    TradeErrorEvent,
)
from ..infra.visualization import MarketVisualizer
import logging
import os
from typing import Any

logger = logging.getLogger("sync-service")

router = APIRouter(tags=["Sync"])

# Template setup
# The dashboard and other HTML files are in the root /app/templates folder
TEMPLATES_DIR = (
    "/app/templates" if os.path.exists("/app/templates") else "../../templates"
)
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/sync_status")
async def get_sync_status(symbol: str = Query(...)):
    return sync_service.get_sync_status(symbol)


@router.get("/check_repair")
async def check_repair(symbol: str = Query(...)):
    return sync_service.check_repair(symbol)


@router.post("/verify_history")
async def verify_history(payload: TradeDBPayload):
    return sync_service.verify_history(
        payload.symbol, payload.gmt_offset, [c.model_dump() for c in payload.candles]
    )


@router.post("/api/backfill")
async def backfill_history(symbol: str, days: int = 7):
    success = await sync_service.backfill_history(symbol, days)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to perform backfill")


@router.post("/api/order")
async def proxy_order(trade: TradeRequest):
    """Proxy order requests to the actual MT5 service."""
    return await mt5_client.place_order(trade.model_dump())


@router.get("/api/positions")
async def get_mt5_positions():
    """Proxy to get current MT5 positions."""
    return await mt5_client.get_positions()


# --- Trading & Event Endpoints ---


@router.post("/report")
async def mt5_report(request: Request, mt5_login: str = Query(...)):
    """Complete position report from MT5."""
    data = await request.json()
    await trading_service.handle_report(mt5_login, data)
    return {"status": "success"}


@router.post("/signal")
async def receive_signal(signal: Any):  # Or use TradingSignal schema
    """Entry point for external signals."""
    from common_events import TradingSignal

    if isinstance(signal, dict):
        signal_obj = TradingSignal(**signal)
    else:
        signal_obj = signal
    await trading_service.broadcast_signal(signal_obj)
    return {"status": "success"}


@router.post("/position_event")
async def position_event(event: PositionEvent, mt5_login: str = Query(...)):
    if event.status == "OPENED":
        await trading_service.handle_position_opened(mt5_login, event)
    elif event.status == "CLOSED":
        await trading_service.handle_position_closed(mt5_login, event)
    return {"status": "success"}


@router.post("/position_opened")
async def position_opened(event: PositionEvent, mt5_login: str = Query(...)):
    await trading_service.handle_position_opened(mt5_login, event)
    return {"status": "success"}


@router.post("/position_closed")
async def position_closed(event: PositionEvent, mt5_login: str = Query(...)):
    await trading_service.handle_position_closed(mt5_login, event)
    return {"status": "success"}


@router.post("/trade_error")
async def trade_error(event: TradeErrorEvent, mt5_login: str = Query(...)):
    await trading_service.handle_trade_error(mt5_login, event)
    return {"status": "success"}


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, symbol: str = "EURUSD", count: int = 288):
    df, latest_signal = sync_service.evaluate_strategy(symbol, count=count)

    if df is None or df.empty:
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "symbol": symbol,
                "total_bars": 0,
                "last_price": "N/A",
                "last_sync": "N/A",
                "chart_html": "<h4>No data found</h4>",
                "latest_signal": latest_signal,
            },
        )

    # 1. Identify overlays (Support, Resistance, EMA)
    overlays = [
        c
        for c in df.columns
        if any(
            p.lower() in c.lower()
            for p in ["Sup_", "Res_", "EMA_", "S1", "R1", "Pivot"]
        )
    ]
    logger.info(f"Dashboard {symbol}: {len(df)} bars, overlays: {overlays}")

    highlights = MarketVisualizer.get_standard_highlights(df)
    fig = MarketVisualizer.get_figure(
        df,
        f"{symbol} Analysis",
        highlights=highlights,
        overlays=overlays,
        show_volume=True,
    )
    chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "symbol": symbol,
            "total_bars": len(df),
            "last_price": f"{df['Close'].iloc[-1]:.5f}",
            "last_sync": df.index[-1].strftime("%Y-%m-%d %H:%M"),
            "chart_html": chart_html,
            "latest_signal": latest_signal,
        },
    )


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request):
    return templates.TemplateResponse("portfolio.html", {"request": request})


@router.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})
