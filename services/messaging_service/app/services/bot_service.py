import httpx
from common_config import get_env_var
from common_logging import setup_logging
from agent import agent_executor
from langchain_core.messages import HumanMessage
import whatsapp.msg_types as msgs
from .whatsapp_service import whatsapp_service

logger = setup_logging("messaging-service")
CORE_SERVICE_URL = get_env_var("CORE_SERVICE_URL", "http://core-service:8001")


class BotService:
    def __init__(self):
        self._commands = {
            "HOLA": self._handle_welcome,
            "COMANDOS": self._handle_list_commands_info,
            "LISTAR COMANDOS": self._handle_list_commands_info,
            "!LOGIN": self._handle_login,
        }

    async def process_request(self, msg):
        response_msgs = [msgs.mark_read_status(msg.id)]

        try:
            async with httpx.AsyncClient() as client:
                # 1. Check if user exists in core service
                resp = await client.get(f"{CORE_SERVICE_URL}/users/{msg.number}")

                if resp.status_code == 404:
                    # User not found, implement simplified signup or redirect
                    # For brevity in this refactor, we'll assume a 'register' endpoint exists or handle it locally
                    logger.info(
                        f"User {msg.number} not found. Triggering registration flow."
                    )
                    # Simplified registration for now
                    await client.post(
                        f"{CORE_SERVICE_URL}/users",
                        params={"phone_number": msg.number, "name": "New User"},
                    )
                    response_msgs.append(
                        msgs.text_message(
                            msg.number,
                            "¡Hola! 👋 Te he registrado automáticamente. ¡Ya puedes empezar!",
                        )
                    )
                    whatsapp_service.send_messages(response_msgs)
                    return

                # Fetch user data (Ensures registration completion)
                resp.json()

            cleaned_text = msg.text.strip().upper()
            found_command = False
            for cmd, handler in self._commands.items():
                if cmd in cleaned_text:
                    result = await handler(msg)
                    if isinstance(result, list):
                        response_msgs.extend(result)
                    else:
                        response_msgs.append(result)
                    found_command = True
                    break

            if not found_command:
                state_input = {
                    "messages": [
                        HumanMessage(content=f"Mi número es {msg.number}. {msg.text}")
                    ]
                }
                result = await agent_executor.ainvoke(
                    state_input, {"recursion_limit": 15}
                )
                agent_reply = result["messages"][-1].content
                response_msgs.append(msgs.text_message(msg.number, agent_reply.strip()))

            whatsapp_service.send_messages(response_msgs)

        except Exception as e:
            logger.exception(f"Error in process_request: {e}")

    async def _handle_welcome(self, msg):
        welcome_text = (
            "¡Hola! 👋 Soy tu *Asistente Financiero AI*.\n\n"
            "Puedo ayudarte a gestionar tu portafolio, configurar alertas de precio y administrar tu cuenta de MetaTrader 5 directamente desde aquí.\n\n"
            "¿En qué puedo ayudarte hoy?"
        )
        return msgs.buttonReply_Message(
            msg, ["🗒️ listar comandos"], welcome_text, "Stonks Bot"
        )

    async def _handle_list_commands_info(self, msg):
        commands_text = (
            "🤖 *Comandos Disponibles:*\n\n"
            "📈 *Trading:* Ver precios, abrir/cerrar posiciones (MT5).\n"
            "🔔 *Alertas:* `Crear alerta EURUSD 1.0850`\n"
            "📋 *Watchlist:* Ver y gestionar tus favoritos.\n"
            "🔐 *Sistemas:* !LOGIN para acceso web.\n\n"
            "💡 *O háblame naturalmente:* '¿Cómo va mi cuenta?' o 'Pon una alerta en Oro'."
        )
        return msgs.buttonReply_Message(msg, ["!LOGIN"], commands_text, "Stonks Bot")

    async def _handle_login(self, msg):
        # Redirect to portfolio login handled by core service
        login_url = f"{get_env_var('APP_URL')}/portfolio/login?phone={msg.number}"
        return msgs.text_message(msg.number, f"🔐 *Acceso Seguro*\n\n{login_url}")


bot_service = BotService()
