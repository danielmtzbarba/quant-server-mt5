import sys
import os
import asyncio
import httpx
import logging
import MetaTrader5 as mt5
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import traceback
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


# --- Logging Setup ---
class ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[94m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[1;91m",
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.msg = f"{color}[MT5-ENGINE]{self.RESET} {record.msg}"
        return super().format(record)


logger = logging.getLogger("mt5-engine")
logger.setLevel(logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(
    ColorFormatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
)
logger.addHandler(sh)


# --- Initialization ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"
BACKEND_URL = os.environ.get("BACKEND_URL", "http://mt5-engine-gcp:8002")

# InfluxDB Configuration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = os.environ.get(
    "INFLUX_TOKEN",
    "X3jsB_yeGU3Il5BINWNYNicYDQ7dkhjbG4PHUAN6yt9XuJHaN8Bj7ROyQr81h-Vwh3Qw6qHNMLF2wylXdaEnFQ==",
)
INFLUX_ORG = os.environ.get("INFLUX_ORG", "danielmtz")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "tradedb")

influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

TRACKED_SYMBOLS = {"EURUSD", "NVDA"}
LAST_CANDLE_TIMES = {}
ACTIVE_POSITIONS = set()


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
    ticket: Optional[int] = None  # Added for CLOSE logic


# --- Background Workers ---
async def position_monitor():
    global ACTIVE_POSITIONS
    logger.info(
        f"Starting Position Monitor Task (5s interval). BACKEND_URL={BACKEND_URL}"
    )
    while True:
        try:
            if not BACKEND_URL:
                await asyncio.sleep(5)
                continue

            pos_tuple = mt5.positions_get()
            current_tickets = (
                set(p.ticket for p in pos_tuple) if pos_tuple is not None else set()
            )
            login = os.environ.get("MT5_LOGIN", "0")

            # Detect OPENED
            opened = current_tickets - ACTIVE_POSITIONS
            for t in opened:
                p = [pos for pos in pos_tuple if pos.ticket == t][0]
                payload = {
                    "ticket": t,
                    "status": "OPENED",
                    "symbol": p.symbol,
                    "type": p.type,
                    "volume": p.volume,
                    "price": p.price_open,
                }
                async with httpx.AsyncClient() as client:
                    url = f"{BACKEND_URL}/position_opened?mt5_login={login}"
                    try:
                        await client.post(url, json=payload, timeout=5)
                        logger.info(f"Webhook pushed: OPENED ticket {t} ({p.symbol})")
                    except Exception as e:
                        logger.error(f"Failed to webhook OPENED: {e}")

            # Detect CLOSED
            closed = ACTIVE_POSITIONS - current_tickets
            for t in closed:
                deals = mt5.history_deals_get(position=t)
                profit = 0.0
                if deals:
                    out_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
                    profit = sum(d.profit for d in out_deals) if out_deals else 0.0

                payload = {"ticket": t, "status": "CLOSED", "profit": profit}
                async with httpx.AsyncClient() as client:
                    url = f"{BACKEND_URL}/position_closed?mt5_login={login}"
                    try:
                        await client.post(url, json=payload, timeout=5)
                        logger.info(
                            f"Webhook pushed: CLOSED ticket {t} (Profit: {profit})"
                        )
                    except Exception as e:
                        logger.error(f"Failed to webhook CLOSED: {e}")

            ACTIVE_POSITIONS = current_tickets
            await asyncio.sleep(5)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Exception in position_monitor: {e}")
            await asyncio.sleep(5)


async def candle_publisher():
    logger.info(f"Starting Candle Publisher Task. BACKEND_URL={BACKEND_URL}")
    while True:
        try:
            if not BACKEND_URL:
                await asyncio.sleep(5)
                continue

            for symbol in list(TRACKED_SYMBOLS):
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 2)
                if rates is None or len(rates) < 2:
                    continue

                last_closed_bar = rates[0]
                bar_time = last_closed_bar["time"]

                if symbol not in LAST_CANDLE_TIMES:
                    LAST_CANDLE_TIMES[symbol] = bar_time
                    continue

                if bar_time > LAST_CANDLE_TIMES[symbol]:
                    LAST_CANDLE_TIMES[symbol] = bar_time
                    ts = (
                        datetime.utcfromtimestamp(bar_time)
                        .strftime("%Y-%m-%d %H:%M:%S")
                        .replace(" ", "T")
                    )

                    payload = {
                        "symbol": symbol,
                        "timeframe": "M1",
                        "gmt_offset": 0,
                        "candles": [
                            {
                                "timestamp": ts,
                                "open": float(last_closed_bar["open"]),
                                "high": float(last_closed_bar["high"]),
                                "low": float(last_closed_bar["low"]),
                                "close": float(last_closed_bar["close"]),
                                "volume": int(last_closed_bar["tick_volume"]),
                            }
                        ],
                    }

                    async with httpx.AsyncClient() as client:
                        login = os.environ.get("MT5_LOGIN", "0")
                        url = f"{BACKEND_URL}/log_candle?mt5_login={login}"
                        try:
                            # 1. Write to Local InfluxDB
                            point = (
                                Point("market_data")
                                .tag("symbol", symbol)
                                .field("open", float(last_closed_bar["open"]))
                                .field("high", float(last_closed_bar["high"]))
                                .field("low", float(last_closed_bar["low"]))
                                .field("close", float(last_closed_bar["close"]))
                                .field("volume", int(last_closed_bar["tick_volume"]))
                                .time(datetime.utcfromtimestamp(bar_time))
                            )
                            write_api.write(bucket=INFLUX_BUCKET, record=point)
                            logger.info(f"Local InfluxDB updated for {symbol} at {ts}")

                            # 2. Notify GCP for Signal/Strategy logic
                            await client.post(url, json=payload, timeout=5)
                            logger.info(
                                f"Signal notification pushed to {url} for {symbol}"
                            )
                        except Exception as e:
                            logger.error(f"Failed to process candle for {symbol}: {e}")

            await asyncio.sleep(1)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Exception in candle_publisher loop: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ACTIVE_POSITIONS
    login_str = os.environ.get("MT5_LOGIN", "")
    password = os.environ.get("MT5_PASSWORD", "")
    server = os.environ.get("MT5_SERVER", "")
    init_params = {"path": MT5_PATH}

    if login_str and password and server:
        init_params.update(
            {"login": int(login_str), "password": password, "server": server}
        )

    if not mt5.initialize(**init_params):
        logger.error(f"MT5 INIT FAILED: {mt5.last_error()}")
    else:
        logger.info("MT5 REST API Initialized via Terminal64.exe natively")

    # Pre-warm ACTIVE_POSITIONS set
    pos_tuple = mt5.positions_get()
    ACTIVE_POSITIONS = (
        set(p.ticket for p in pos_tuple) if pos_tuple is not None else set()
    )
    logger.info(
        f"Pre-warmed {len(ACTIVE_POSITIONS)} active positions from MetaTrader 5."
    )

    task_c = asyncio.create_task(candle_publisher())
    task_p = asyncio.create_task(position_monitor())

    yield
    task_c.cancel()
    task_p.cancel()
    mt5.shutdown()


app = FastAPI(title="MT5 Engine Headless REST API", lifespan=lifespan)


# --- MT5 State & Administration Endpoints ---


@app.get("/api/health")
def health_check():
    info = mt5.terminal_info()
    if info is None:
        logger.error("Health Check requested: MT5 Terminal Information unavailable.")
        return {"status": "unhealthy", "error": mt5.last_error()}
    logger.info("Health Check Success.")
    return {"status": "healthy", "terminal": info._asdict()}


@app.get("/api/positions")
def get_positions():
    pos = mt5.positions_get()
    logger.info(
        f"Positions requested. Returning {len(pos) if pos else 0} active positions."
    )
    if pos is None:
        return []
    return [p._asdict() for p in pos]


# --- Dynamic Symbol Tracking ---


@app.post("/api/symbols")
def set_symbols(symbols: List[str]):
    global TRACKED_SYMBOLS
    TRACKED_SYMBOLS.clear()
    for s in symbols:
        TRACKED_SYMBOLS.add(s.upper())
    logger.info(
        f"Updated dynamic tracking. Now streaming M1 candles for: {list(TRACKED_SYMBOLS)}"
    )
    return {"status": "success", "tracked": list(TRACKED_SYMBOLS)}


@app.get("/api/symbols")
def get_symbols():
    return {"tracked": list(TRACKED_SYMBOLS)}


@app.get("/api/history")
def get_history(symbol: str, count: int = 1000):
    rates = mt5.copy_rates_from_pos(symbol.upper(), mt5.TIMEFRAME_M1, 0, count)
    if rates is None:
        logger.warning(f"History retrieval failed for {symbol}.")
        raise HTTPException(status_code=404, detail="No rates found or invalid symbol")

    candles = []
    for r in rates:
        ts = (
            datetime.utcfromtimestamp(r["time"])
            .strftime("%Y-%m-%d %H:%M:%S")
            .replace(" ", "T")
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

    logger.info(f"Exported {len(candles)} historical candles for {symbol.upper()}.")
    return {
        "symbol": symbol.upper(),
        "timeframe": "M1",
        "gmt_offset": 0,
        "candles": candles,
    }


@app.post("/api/backfill")
async def backfill_history(symbol: str, days: int = 7):
    symbol = symbol.upper()
    count = days * 1440  # M1 bars in a day
    logger.info(f"Starting backfill for {symbol}: {days} days ({count} bars)")

    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, count)
    if rates is None:
        logger.error(f"Backfill failed: Symbol {symbol} not found or no rates.")
        raise HTTPException(status_code=404, detail="No rates found")

    points = []
    for r in rates:
        point = (
            Point("market_data")
            .tag("symbol", symbol)
            .field("open", float(r["open"]))
            .field("high", float(r["high"]))
            .field("low", float(r["low"]))
            .field("close", float(r["close"]))
            .field("volume", int(r["tick_volume"]))
            .time(datetime.utcfromtimestamp(r["time"]))
        )
        points.append(point)

    try:
        # Batch write in chunks to avoid memory/timeout issues
        chunk_size = 1000
        for i in range(0, len(points), chunk_size):
            write_api.write(bucket=INFLUX_BUCKET, record=points[i : i + chunk_size])

        logger.info(f"Backfill SUCCESS for {symbol}. Ingested {len(points)} points.")
        return {"status": "success", "inserted": len(points)}
    except Exception as e:
        logger.error(f"Failed to write backfill to InfluxDB: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Execution Controller ---


@app.post("/api/order")
def place_order(trade: TradeRequest):
    try:
        action = trade.action.upper()

        # --- EXPLICIT CLOSE LOGIC ---
        if action == "CLOSE":
            if not trade.ticket:
                logger.error(
                    "Order rejected: Action string is 'CLOSE' but no ticket was provided."
                )
                raise HTTPException(
                    status_code=400, detail="Missing ticket for CLOSE action"
                )
            pos = mt5.positions_get(ticket=trade.ticket)
            if pos is None or len(pos) == 0:
                logger.error(
                    f"Order rejected: Could not find active MT5 position matching ticket {trade.ticket}"
                )
                raise HTTPException(
                    status_code=404, detail=f"Position {trade.ticket} not found"
                )

            p = pos[0]
            symbol = p.symbol
            order_type = (
                mt5.ORDER_TYPE_SELL
                if p.type == mt5.ORDER_TYPE_BUY
                else mt5.ORDER_TYPE_BUY
            )
            tick = mt5.symbol_info_tick(symbol)
            price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
            volume = p.volume

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "position": trade.ticket,
                "price": price,
                "magic": trade.magic,
                "comment": "API Native Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            logger.info(
                f"Intercepted CLOSE command for Ticket {trade.ticket}. Reversing {p.volume} volume on {symbol}."
            )

        # --- EXPLICIT OPEN (BUY/SELL) LOGIC ---
        else:
            if not trade.symbol:
                logger.error(
                    "Order rejected: Action is BUY/SELL but no symbol was provided."
                )
                raise HTTPException(
                    status_code=400, detail="Missing symbol for BUY/SELL action"
                )

            symbol = trade.symbol.upper()
            order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL

            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                logger.error(
                    f"Order rejected: Broker failed to resolve pricing tick data for {symbol}."
                )
                raise HTTPException(
                    status_code=400, detail=f"No tick data for {symbol}"
                )

            price = trade.price or (
                tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
            )

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

            if trade.sl is not None:
                request["sl"] = trade.sl
            if trade.tp is not None:
                request["tp"] = trade.tp

            logger.info(
                f"Intercepted {action} command for {trade.volume} lot(s) on {symbol}."
            )

        logger.info(f"Dispatching MT5 execution payload: {request}")
        result = mt5.order_send(request)

        if result is None:
            last_err = mt5.last_error()
            logger.critical(
                f"FATAL: mt5.order_send() catastrophically failed. None output. {last_err}"
            )
            raise HTTPException(
                status_code=500, detail=f"MT5 order_send returned None: {last_err}"
            )

        logger.info(
            f"Execution Result >> Return Code: {result.retcode} | Comment: {result.comment}"
        )
        return {
            "status": "success"
            if result.retcode == mt5.TRADE_RETCODE_DONE
            else "failed",
            "retcode": result.retcode,
            "comment": result.comment,
            "ticket": result.order,
            "error_code": mt5.last_error(),
        }
    except Exception as e:
        logger.error(f"Unexpected Exception during order execution: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
