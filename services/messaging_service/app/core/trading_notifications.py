import logging
from ..infra.whatsapp import msg_types as msgs
from .whatsapp_service import whatsapp_service

logger = logging.getLogger("messaging-service")


class TradingNotificationManager:
    """Centralized manager for all trading-related WhatsApp templates."""

    async def notify(self, phone: str, event_type: str, data: dict):
        """Dispatches a notification based on event type."""
        logger.info(f"Notification Request: {event_type} for {phone}")

        handler = getattr(self, f"_handle_{event_type.lower()}", self._handle_unknown)
        message_json = await handler(phone, data)

        if message_json:
            whatsapp_service.send_messages([message_json])

    async def _handle_signal(self, phone: str, data: dict):
        """Format a trading signal notification."""
        action = data.get("action", "UNK").upper()
        symbol = data.get("symbol", "UNK").upper()
        price = data.get("price", 0.0)

        emoji = "📈" if action == "BUY" else "📉"

        text = (
            f"{emoji} *SIGNAL: {action} {symbol}*\n"
            f"Price: {price:.5f}\n\n"
            f"_Your authorized terminal will process this order automatically._"
        )
        return msgs.text_message(phone, text)

    async def _handle_opened(self, phone: str, data: dict):
        """Format a trade opened notification."""
        ticket = data.get("ticket", "UNK")
        symbol = data.get("symbol", "UNK").upper()
        price = data.get("price", 0.0)
        side = "BUY" if data.get("type", 0) == 0 else "SELL"

        text = (
            f"✅ *TRADE OPENED*\n\n"
            f"Ticket: {ticket}\n"
            f"Action: {side}\n"
            f"Symbol: {symbol}\n"
            f"Price: {price:.5f}"
        )
        return msgs.text_message(phone, text)

    async def _handle_closed(self, phone: str, data: dict):
        """Format a trade closed notification."""
        ticket = data.get("ticket", "UNK")
        symbol = data.get("symbol", "UNK").upper()
        profit = data.get("profit", 0.0)

        emoji = "🏁" if profit >= 0 else "❌"
        status = "PROFIT" if profit >= 0 else "LOSS"

        text = (
            f"{emoji} *TRADE CLOSED*\n\n"
            f"Ticket: {ticket}\n"
            f"Symbol: {symbol}\n"
            f"Result: {status} (${profit:.2f})"
        )
        return msgs.text_message(phone, text)

    async def _handle_error(self, phone: str, data: dict):
        """Format a trade error notification."""
        action = data.get("action", "UNK").upper()
        symbol = data.get("symbol", "UNK").upper()
        message = data.get("message", "Unknown Error")

        text = (
            f"⚠️ *TRADE ERROR*\n\n"
            f"Action: {action}\n"
            f"Symbol: {symbol}\n"
            f"Reason: *{message}*"
        )
        return msgs.text_message(phone, text)

    async def _handle_unknown(self, phone: str, data: dict):
        logger.warning(f"Unknown event type received for notification: {data}")
        return None


notification_manager = TradingNotificationManager()
