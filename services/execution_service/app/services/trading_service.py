import httpx
from execution_queue.queue import mt5_queue
from trade_db.api import MarketDataAPI
from common_logging import setup_logging
from common_config import get_env_var
from common_events import TradingSignal, PositionEvent

logger = setup_logging("execution-service", tag="TRADING", color="green")

CORE_SERVICE_URL = get_env_var("CORE_SERVICE_URL", "http://127.0.0.1:8001")
MESSAGING_SERVICE_URL = get_env_var("MESSAGING_SERVICE_URL", "http://127.0.0.1:8003")
MAX_POSITIONS = int(get_env_var("MAX_POSITIONS", "5"))


class TradingService:
    def __init__(self):
        self.market_data = MarketDataAPI()
        self.last_report = []

    def queue_mt5_command(self, action: str, **kwargs):
        """Add a command to the MT5 execution queue."""
        mt5_queue.queue_command(action, **kwargs)

    def get_next_mt5_command(self):
        """Retrieve and remove the next command from the queue."""
        return mt5_queue.get_next()

    async def broadcast_signal(self, signal: TradingSignal) -> tuple[bool, str]:
        """Standard flow for all signals (Automated or Manual)."""
        symbol = signal.symbol.upper()

        async with httpx.AsyncClient() as client:
            try:
                # 1. Gatekeeper: Check max positions
                count_resp = await client.get(
                    f"{CORE_SERVICE_URL}/positions/active/count"
                )
                if count_resp.status_code == 200:
                    current_count = count_resp.json().get("count", 0)
                    if current_count >= MAX_POSITIONS:
                        msg = f"GATED: Max positions reached ({current_count}/{MAX_POSITIONS}). Skipping {symbol}"
                        logger.warning(msg)
                        return False, "MAX_POSITIONS_REACHED"

                # 2. Create PENDING Order in DB
                import time
                order_id = int(time.time() * 1000)
                order_payload = {
                    "id": order_id,
                    "broker_account_id": 1,  # Default
                    "symbol": symbol,
                    "action": signal.action.upper(),
                    "quantity": getattr(signal, "volume", 0.01),
                    "price": signal.price,
                    "status": "PENDING",
                }
                await client.post(f"{CORE_SERVICE_URL}/orders", json=order_payload)

                # 3. Queue MT5 Command
                logger.info(f"Queuing MT5 {signal.action} for {symbol}")
                self.queue_mt5_command(
                    signal.action.upper(),
                    symbol=symbol,
                    volume=getattr(signal, "volume", 0.01),
                    price=signal.price,
                    sl=signal.sl,
                    tp=signal.tp,
                )

                return True, "QUEUED"

            except Exception as e:
                logger.error(f"Error in broadcast_signal flow: {e}")
                return False, str(e)

    async def handle_report(self, positions_data: list):
        """Process MT5 position report and update core service."""
        self.last_report = positions_data
        logger.info(f"Processing MT5 report: {len(positions_data)} positions")
        async with httpx.AsyncClient() as client:
            try:
                logger.info("Server ➔ DB: SYNC Positions")
                # Using account_id=1 as default for local dev
                await client.post(
                    f"{CORE_SERVICE_URL}/positions/sync",
                    params={"account_id": 1},
                    json=positions_data,
                )
            except Exception as e:
                logger.error(f"Error syncing report: {e}")

    async def handle_position_opened(self, event: PositionEvent):
        """Handle real-time notification of a new position."""
        logger.info(f"Server ➔ DB: CREATE Position {event.ticket} {event.symbol}")
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{CORE_SERVICE_URL}/positions/open",
                    json={
                        "ticket": event.ticket,
                        "symbol": event.symbol,
                        "volume": event.volume,
                        "price": event.price,
                        "type": event.type,
                    },
                )
                # 2. Notify user for confirmation
                user_resp = await client.get(f"{CORE_SERVICE_URL}/accounts/1/user")
                if user_resp.status_code == 200:
                    user = user_resp.json()
                    phone = user.get("phone_number")
                    if phone:
                        side = (
                            "BUY"
                            if event.type == 0
                            else "SELL"
                            if event.type == 1
                            else "TRADE"
                        )
                        msg = (
                            f"✅ *TRADE OPENED*\n\n"
                            f"Ticket: {event.ticket}\n"
                            f"Action: {side}\n"
                            f"Symbol: {event.symbol}\n"
                            f"Price: {event.price}"
                        )
                        await client.post(
                            f"{MESSAGING_SERVICE_URL}/send",
                            json={"to": phone, "text": msg},
                        )
            except Exception as e:
                logger.error(f"Error handling opened position: {e}")

    async def handle_position_closed(self, event: PositionEvent):
        """Handle real-time notification of a closed position."""
        logger.info(
            f"Server ➔ DB: UPDATE Position {event.ticket} (CLOSED) Profit: {event.profit}"
        )
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{CORE_SERVICE_URL}/positions/close",
                    params={"ticket": event.ticket, "profit": event.profit or 0.0},
                )
                # 2. Notify user for confirmation
                user_resp = await client.get(f"{CORE_SERVICE_URL}/accounts/1/user")
                if user_resp.status_code == 200:
                    user = user_resp.json()
                    phone = user.get("phone_number")
                    if phone:
                        msg = (
                            f"🏁 *TRADE CLOSED*\n\n"
                            f"Ticket: {event.ticket}\n"
                            f"Symbol: {event.symbol or 'UNK'}\n"
                            f"Profit: ${event.profit:.2f}"
                        )
                        await client.post(
                            f"{MESSAGING_SERVICE_URL}/send",
                            json={"to": phone, "text": msg},
                        )
            except Exception as e:
                logger.error(f"Error handling closed position: {e}")

    async def check_signals(self, symbol: str):
        """Unified strategy evaluation and signal broadcasting."""
        try:
            from trade_db.indicators import PriceActionIndicators as Indicators
            from trade_db.strategy import PriceActionStrategy as Strategy

            # 1. Fetch resampled data (e.g. 15m)
            df = self.market_data.get_resampled_candles(
                symbol, interval="15m", start="-3d"
            )
            if df.empty:
                logger.debug(f"No resampled data for {symbol} to check signals.")
                return

            # 2. Add indicators
            df = Indicators.add_dynamic_support_resistance(df, window=50)
            df = Indicators.add_atr(df, period=14)

            # 3. Get current signal
            signal_data = Strategy.get_current_signal(
                df, sup_col="Sup_50", res_col="Res_50", atr_col="ATR_14"
            )

            if signal_data and signal_data.get("action") != "HOLD":
                logger.info(f"Strategy Triggered: {signal_data['action']} for {symbol}")
                # Map to TradingSignal model
                signal = TradingSignal(
                    symbol=symbol,
                    action=signal_data["action"],
                    price=df["Close"].iloc[-1],
                    sl=signal_data.get("stop_loss"),
                    tp=signal_data.get("take_profit"),
                    timestamp=df.index[-1].isoformat(),
                )
                await self.broadcast_signal(signal)

        except Exception as e:
            logger.error(f"Error checking signals for {symbol}: {e}")


trading_service = TradingService()
