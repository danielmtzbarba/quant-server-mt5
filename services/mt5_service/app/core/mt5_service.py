import MetaTrader5 as mt5
from typing import Optional, Set
import logging
from .config import settings
from ..models.schemas import TradeRequest, OrderResponse
import traceback

logger = logging.getLogger("mt5-service")


class MT5Service:
    def __init__(self):
        self.active_positions: Set[int] = set()
        self.tracked_symbols: Set[str] = {"EURUSD", "NVDA"}
        self.last_candle_times: dict = {}

    def initialize(self) -> bool:
        init_params = {"path": settings.MT5_PATH}
        if settings.MT5_LOGIN != "0" and settings.MT5_PASSWORD and settings.MT5_SERVER:
            init_params.update(
                {
                    "login": int(settings.MT5_LOGIN),
                    "password": settings.MT5_PASSWORD,
                    "server": settings.MT5_SERVER,
                }
            )

        if not mt5.initialize(**init_params):
            logger.error(f"MT5 INIT FAILED: {mt5.last_error()}")
            return False

        logger.info(f"MT5 REST API Initialized via {settings.MT5_PATH}")
        self._warm_positions()
        return True

    def _warm_positions(self):
        pos_tuple = mt5.positions_get()
        self.active_positions = (
            set(p.ticket for p in pos_tuple) if pos_tuple is not None else set()
        )
        logger.info(f"Pre-warmed {len(self.active_positions)} active positions.")

    def shutdown(self):
        mt5.shutdown()

    def get_terminal_info(self):
        return mt5.terminal_info()

    def get_gmt_offset(self) -> int:
        """
        Calculates the GMT offset of the broker server time relative to UTC.
        Compares the latest quote time from a liquid symbol (EURUSD) with the system (UTC) time.
        """
        import time

        tick = mt5.symbol_info_tick("EURUSD")
        if not tick:
            return 0

        # broker_time is the unix timestamp of the last tick (on broker terms)
        broker_time = float(tick.time)
        utc_now = time.time()

        # Calculate the difference and round to the nearest hour (3600s)
        # Broker Time = UTC + Offset -> Offset = Broker Time - UTC
        offset_seconds = round((broker_time - utc_now) / 3600) * 3600
        return int(offset_seconds)

    def get_positions(self, ticket: Optional[int] = None):
        if ticket:
            return mt5.positions_get(ticket=ticket)
        return mt5.positions_get()

    def place_order(self, trade: TradeRequest) -> OrderResponse:
        try:
            action = trade.action.upper()
            if action == "CLOSE":
                return self._close_order(trade)
            else:
                return self._open_order(trade)
        except Exception as e:
            logger.error(f"Unexpected Exception during order execution: {e}")
            traceback.print_exc()
            return OrderResponse(
                status="failed",
                retcode=-1,
                comment=str(e),
                error_code=mt5.last_error()[0] if mt5.last_error() else 0,
            )

    def _close_order(self, trade: TradeRequest) -> OrderResponse:
        if not trade.ticket:
            return OrderResponse(
                status="failed",
                retcode=-1,
                comment="Missing ticket for CLOSE",
                error_code=0,
            )

        pos = mt5.positions_get(ticket=trade.ticket)
        if pos is None or len(pos) == 0:
            return OrderResponse(
                status="failed",
                retcode=-1,
                comment=f"Position {trade.ticket} not found",
                error_code=0,
            )

        p = pos[0]
        order_type = (
            mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        )
        tick = mt5.symbol_info_tick(p.symbol)
        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": p.symbol,
            "volume": p.volume,
            "type": order_type,
            "position": trade.ticket,
            "price": price,
            "magic": trade.magic,
            "comment": "API Native Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        return self._send_request(request)

    def _open_order(self, trade: TradeRequest) -> OrderResponse:
        if not trade.symbol:
            return OrderResponse(
                status="failed",
                retcode=-1,
                comment="Missing symbol for BUY/SELL",
                error_code=0,
            )

        symbol = trade.symbol.upper()
        action = trade.action.upper()
        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return OrderResponse(
                status="failed",
                retcode=-1,
                comment=f"No tick data for {symbol}",
                error_code=0,
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

        return self._send_request(request)

    def _send_request(self, request: dict) -> OrderResponse:
        result = mt5.order_send(request)
        if result is None:
            return OrderResponse(
                status="failed",
                retcode=-1,
                comment="MT5 returned None",
                error_code=mt5.last_error()[0],
            )

        return OrderResponse(
            status="success" if result.retcode == mt5.TRADE_RETCODE_DONE else "failed",
            retcode=result.retcode,
            comment=result.comment,
            ticket=result.order,
            error_code=mt5.last_error()[0],
        )

    def fetch_rates(self, symbol: str, count: int, timeframe=mt5.TIMEFRAME_M1):
        return mt5.copy_rates_from_pos(symbol.upper(), timeframe, 0, count)


mt5_service = MT5Service()
