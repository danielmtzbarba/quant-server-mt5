import httpx
from trade_db.api import MarketDataAPI
from common_logging import setup_logging
from common_config import get_env_var
from common_events import TradingSignal, PositionEvent, TradeErrorEvent

logger = setup_logging("execution-service", tag="TRADING", color="green")

CORE_SERVICE_URL = get_env_var("CORE_SERVICE_URL", "http://127.0.0.1:8001")
MESSAGING_SERVICE_URL = get_env_var("MESSAGING_SERVICE_URL", "http://127.0.0.1:8003")
MT5_ENGINE_URL = get_env_var("MT5_ENGINE_URL", "http://mt5-engine-azure:8000")
MAX_POSITIONS = int(get_env_var("MAX_POSITIONS", "5"))


class TradingService:
    def __init__(self):
        self.market_data = MarketDataAPI()
        self.last_report = []

    async def broadcast_signal(self, signal: TradingSignal) -> tuple[bool, str]:
        """Multi-tenant distribution: Sends signals only to subscribed and completed users."""
        from utils.strategy import SRBounceRejection

        symbol = signal.symbol.upper()
        # Strategy name is derived from where the signal is coming from
        strategy_name = SRBounceRejection.strategy_id

        async with httpx.AsyncClient() as client:
            try:
                # 0. Gatekeeper: Check max global positions
                count_resp = await client.get(
                    f"{CORE_SERVICE_URL}/positions/active/count"
                )
                if count_resp.status_code == 200:
                    current_count = count_resp.json().get("count", 0)
                    if current_count >= MAX_POSITIONS:
                        logger.warning(
                            f"GATING: Max positions reached ({current_count}/{MAX_POSITIONS}). Skipping {symbol}"
                        )
                        return False, "MAX_POSITIONS_REACHED"

                # 1. Fetch Subscribed and COMPLETED Users
                sub_resp = await client.get(
                    f"{CORE_SERVICE_URL}/strategies/{strategy_name}/subscribers"
                )
                if sub_resp.status_code != 200:
                    logger.error(f"Failed to fetch subscribers: {sub_resp.text}")
                    return False, "FETCH_SUBSCRIBERS_FAILED"

                subscribers = sub_resp.json()
                logger.info(
                    f"Broadcasting {strategy_name} signal for {symbol} to {len(subscribers)} subscribers"
                )

                for user in subscribers:
                    # 1. Notify via WhatsApp
                    phone = user.get("phone_number")
                    if phone:
                        msg = (
                            f"📈 *SIGNAL: {signal.action} {symbol}*\n"
                            f"Price: {signal.price:.5f}\n\n"
                            f"_Tu terminal autorizada procesará esta orden automáticamente._"
                        )
                        await client.post(
                            f"{MESSAGING_SERVICE_URL}/send",
                            json={"to": phone, "text": msg},
                        )

                    # 2. Iterate and authorize broker accounts
                    for acc in user.get("broker_accounts", []):
                        acc_id = acc["id"]
                        login = acc["account_number"]

                        # Create PENDING Order in DB linked to this account
                        import time

                        order_id = int(time.time() * 1000)
                        order_payload = {
                            "id": order_id,
                            "broker_account_id": acc_id,
                            "symbol": symbol,
                            "action": signal.action.upper(),
                            "quantity": getattr(signal, "volume", 0.01),
                            "price": signal.price,
                            "status": "PENDING",
                        }
                        await client.post(
                            f"{CORE_SERVICE_URL}/orders", json=order_payload
                        )

                        # Instantaneous execution command directly to the specific Tailscale IP Engine
                        logger.info(
                            f"Executing TRADE directly on {login}'s MT5 Engine ({user.get('name')})"
                        )
                        mt5_payload = {
                            "action": signal.action.upper(),
                            "symbol": symbol,
                            "volume": getattr(signal, "volume", 0.01),
                            "price": signal.price,
                        }

                        try:
                            # Use internal Tailscale network layer logic for immediate fulfillment
                            trade_resp = await client.post(
                                f"{MT5_ENGINE_URL}/api/order",
                                json=mt5_payload,
                                timeout=10.0,
                            )
                            if trade_resp.status_code == 200:
                                res_data = trade_resp.json()
                                if res_data.get("status") == "success":
                                    logger.info(
                                        f"Trade successful! Ticket: {res_data.get('ticket')}"
                                    )
                                else:
                                    logger.error(f"Trade rejected by MT5: {res_data}")
                            else:
                                logger.error(
                                    f"MT5 API Failed: {trade_resp.status_code} {trade_resp.text}"
                                )
                        except Exception as mt5_err:
                            logger.error(
                                f"Network error trying to reach MT5 Engine: {mt5_err}"
                            )

                return True, "BROADCASTED"

            except Exception as e:
                logger.error(f"Error in broadcast_signal flow: {e}")
                return False, str(e)

    async def handle_report(self, mt5_login: str, positions_data: list):
        """Process MT5 position report and update core service for specific login."""
        self.last_report = positions_data
        logger.info(
            f"Processing MT5 report for {mt5_login}: {len(positions_data)} positions"
        )
        async with httpx.AsyncClient() as client:
            try:
                # Resolve account_id from mt5_login
                acc_resp = await client.get(
                    f"{CORE_SERVICE_URL}/accounts/verify/{mt5_login}"
                )
                if acc_resp.status_code == 404:
                    logger.warning(
                        f"UNAUTHORIZED TERMINAL: Login {mt5_login} not found in DB."
                    )
                    return

                account_id = acc_resp.json()["id"]
                logger.info(f"Server ➔ DB: SYNC Positions (Account {account_id})")
                await client.post(
                    f"{CORE_SERVICE_URL}/positions/sync",
                    params={"account_id": account_id},
                    json=positions_data,
                )
            except Exception as e:
                logger.error(f"Error syncing report for {mt5_login}: {e}")

    async def handle_position_opened(self, mt5_login: str, event: PositionEvent):
        """Handle real-time notification of a new position for a specific login."""
        logger.info(
            f"Server ➔ DB: CREATE Position {event.ticket} {event.symbol} for {mt5_login}"
        )
        async with httpx.AsyncClient() as client:
            try:
                # 1. Resolve Account
                acc_resp = await client.get(
                    f"{CORE_SERVICE_URL}/accounts/verify/{mt5_login}"
                )
                if acc_resp.status_code == 404:
                    return

                account_id = acc_resp.json()["id"]
                user_id = acc_resp.json()["user_id"]

                await client.post(
                    f"{CORE_SERVICE_URL}/positions/open",
                    json={
                        "ticket": event.ticket,
                        "broker_account_id": account_id,
                        "symbol": event.symbol,
                        "volume": event.volume,
                        "price": event.price,
                        "type": event.type,
                    },
                )
                # 2. Notify user for confirmation
                user_resp = await client.get(f"{CORE_SERVICE_URL}/users/id/{user_id}")
                if user_resp.status_code == 200:
                    user = user_resp.json()
                    phone = user.get("phone_number")
                    if phone:
                        side = "BUY" if event.type == 0 else "SELL"
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

    async def handle_position_closed(self, mt5_login: str, event: PositionEvent):
        """Handle real-time notification of a closed position for a specific login."""
        logger.info(
            f"Server ➔ DB: UPDATE Position {event.ticket} (CLOSED) Profit: {event.profit}"
        )
        async with httpx.AsyncClient() as client:
            try:
                # Simply update based on ticket (ticket is global to MT5)
                await client.post(
                    f"{CORE_SERVICE_URL}/positions/close",
                    params={"ticket": event.ticket, "profit": event.profit or 0.0},
                )

                # Get user for notification
                acc_resp = await client.get(
                    f"{CORE_SERVICE_URL}/accounts/verify/{mt5_login}"
                )
                if acc_resp.status_code == 200:
                    user_id = acc_resp.json()["user_id"]
                    user_resp = await client.get(
                        f"{CORE_SERVICE_URL}/users/id/{user_id}"
                    )
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

    async def handle_trade_error(self, mt5_login: str, event: TradeErrorEvent):
        """Handle real-time notification of a failed trade execution."""
        logger.warning(
            f"Trade Error for {mt5_login}: {event.action} {event.symbol} -> {event.message}"
        )
        async with httpx.AsyncClient() as client:
            try:
                # Resolve Account ➔ User
                acc_resp = await client.get(
                    f"{CORE_SERVICE_URL}/accounts/verify/{mt5_login}"
                )
                if acc_resp.status_code == 200:
                    user_id = acc_resp.json()["user_id"]
                    user_resp = await client.get(
                        f"{CORE_SERVICE_URL}/users/id/{user_id}"
                    )
                    if user_resp.status_code == 200:
                        user = user_resp.json()
                        phone = user.get("phone_number")
                        if phone:
                            msg = (
                                f"❌ *TRADE FAILED*\n\n"
                                f"Action: {event.action}\n"
                                f"Symbol: {event.symbol}\n"
                                f"Reason: *{event.message}*\n"
                                f"Code: {event.retcode}"
                            )
                            await client.post(
                                f"{MESSAGING_SERVICE_URL}/send",
                                json={"to": phone, "text": msg},
                            )
            except Exception as e:
                logger.error(f"Error handling trade error: {e}")

    async def check_signals(self, symbol: str):
        """Unified strategy evaluation and signal broadcasting."""
        try:
            from utils.indicators import PriceActionIndicators as Indicators
            from utils.strategy import SRBounceRejection as Strategy
            from utils.trading_utils import filter_last_trading_days

            # 1. Over-fetch (e.g. 7 days) to ensure we find at least 3 trading sessions
            # This guarantees context for indicators even on a Monday morning.
            df_raw = self.market_data.get_resampled_candles(
                symbol, interval="15m", start="-7d"
            )

            # 2. Slice to exactly the last 3 trading days
            df = filter_last_trading_days(df_raw, n_days=3)

            if df is None or df.empty:
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
