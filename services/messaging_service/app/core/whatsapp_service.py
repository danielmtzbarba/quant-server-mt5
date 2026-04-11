import json
import logging
from ..infra.whatsapp import utils as wa

logger = logging.getLogger("messaging-service")


class WhatsAppService:
    def send_messages(self, messages: list):
        """Sends a list of messages via WhatsApp."""
        for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi"]:
            log = logging.getLogger(name)
            log.handlers = []
            log.propagate = False

        try:
            while len(messages) > 0:
                m = messages.pop(0)

                m_data = m
                if isinstance(m, str):
                    try:
                        m_data = json.loads(m)
                    except json.JSONDecodeError:
                        pass

                # Log outgoing messages
                if isinstance(m_data, dict) and "to" in m_data:
                    logger.info(f"Server ➔ User ({m_data['to']})")

                wa.send_message(m)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")


whatsapp_service = WhatsAppService()
