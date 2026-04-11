import httpx
import logging
from common_config import get_env_var
from .agent.agent_graph import get_agent_executor_singleton
from langchain_core.messages import HumanMessage
from ..infra.whatsapp import msg_types as msgs
from .whatsapp_service import whatsapp_service

logger = logging.getLogger("messaging-service")
CORE_SERVICE_URL = get_env_var("CORE_SERVICE_URL", "http://core-service:8001")


class BotService:
    def __init__(self):
        self._commands = {
            "HOLA": self._handle_welcome,
            "COMANDOS": self._handle_list_commands_info,
            "LISTAR COMANDOS": self._handle_list_commands_info,
            "!LOGIN": self._handle_login,
            "ESTRATEGIAS": self._handle_list_strategies,
            "SUSCRIBIR": self._handle_subscribe,
        }

    async def process_request(self, msg):
        response_msgs = [msgs.mark_read_status(msg.id)]

        try:
            async with httpx.AsyncClient() as client:
                # 1. Check if user exists in core service
                resp = await client.get(f"{CORE_SERVICE_URL}/users/{msg.number}")

                if resp.status_code == 404:
                    logger.info(
                        f"User {msg.number} not found. Initializing atomic signup flow."
                    )
                    signup_resp = await client.post(
                        f"{CORE_SERVICE_URL}/users/signup/init",
                        params={"phone_number": msg.number},
                    )

                    if signup_resp.status_code == 200:
                        response_msgs.append(
                            msgs.text_message(
                                msg.number,
                                "¡Hola! 👋 Veo que eres nuevo. Para empezar, dime: *¿Cuál es tu nombre de usuario?*",
                            )
                        )
                    else:
                        logger.error(
                            f"Failed to initialize signup for {msg.number}: {signup_resp.text}"
                        )
                        response_msgs.append(
                            msgs.text_message(
                                msg.number,
                                "Lo siento, hubo un error técnico al registrarte.",
                            )
                        )
                    whatsapp_service.send_messages(response_msgs)
                    return

                user = resp.json()

                # 2. Check Signup Session state
                session_resp = await client.get(
                    f"{CORE_SERVICE_URL}/signup/session/{msg.number}"
                )
                if session_resp.status_code == 200:
                    session = session_resp.json()
                    if not session.get("completed"):
                        result = await self._handle_signup_step(msg, session, user)
                        response_msgs.append(result)
                        whatsapp_service.send_messages(response_msgs)
                        return

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
                # Check if user tapped a strategy-name button to auto-subscribe
                async with httpx.AsyncClient() as client:
                    strategies_resp = await client.get(f"{CORE_SERVICE_URL}/strategies")
                    if strategies_resp.status_code == 200:
                        known_names = [
                            s["name"].upper() for s in strategies_resp.json()
                        ]
                        if cleaned_text in known_names:
                            # Synthesize a SUSCRIBIR command
                            class _FakeMsg:
                                number = msg.number
                                text = f"SUSCRIBIR {cleaned_text}"

                            result = await self._handle_subscribe(_FakeMsg())
                            response_msgs.append(result)
                            whatsapp_service.send_messages(response_msgs)
                            return

                state_input = {
                    "messages": [
                        HumanMessage(content=f"Mi número es {msg.number}. {msg.text}")
                    ]
                }
                result = await get_agent_executor_singleton().ainvoke(
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
            "📈 *Trading:* Ver precios y operar (MT5).\n"
            "📊 *Estrategias:* `ESTRATEGIAS` para ver opciones.\n"
            "✅ *Suscripción:* `SUSCRIBIR [NOMBRE]` para recibir señales.\n"
            "🔔 *Alertas:* `Crear alerta EURUSD 1.0850`\n"
            "📋 *Watchlist:* Ver y gestionar tus favoritos.\n"
            "🔐 *Sistemas:* !LOGIN para acceso web.\n\n"
            "💡 *O háblame naturalmente:* '¿Cómo va mi cuenta?'"
        )
        return msgs.buttonReply_Message(
            msg, ["ESTRATEGIAS", "!LOGIN"], commands_text, "Stonks Bot"
        )

    async def _handle_signup_step(self, msg, session, user):
        """Conversational step-by-step handler for new users."""
        async with httpx.AsyncClient() as client:
            current_step = session.get("step")

            if current_step == "ASK_NAME":
                name = msg.text.strip()
                await client.patch(
                    f"{CORE_SERVICE_URL}/signup/session/{msg.number}",
                    json={"name": name, "step": "ASK_BROKER_ID"},
                )
                return msgs.text_message(
                    msg.number,
                    f"¡Mucho gusto, *{name}*! 👋\n\nAhora, por favor ingresa tu **ID de cuenta de MetaTrader 5** (el número de login) para vincular tu terminal.",
                )

            if current_step == "ASK_BROKER_ID":
                broker_id = msg.text.strip()
                # Create broker account
                resp = await client.post(
                    f"{CORE_SERVICE_URL}/broker_accounts",
                    params={
                        "user_id": user["id"],
                        "account_number": broker_id,
                        "broker_name": "MetaTrader 5",
                        "account_type": "MT5",
                    },
                )
                if resp.status_code == 200:
                    await client.patch(
                        f"{CORE_SERVICE_URL}/signup/session/{msg.number}",
                        json={"step": "ASK_PORTFOLIO_PREFS"},
                    )
                    return msgs.text_message(
                        msg.number,
                        "✅ *¡Terminal Vinculada!*\n\nÚltimo paso: ¿Qué mercados te interesa operar?\n\nResponde **FX**, **STOCKS** o **AMBOS**.",
                    )
                else:
                    return msgs.text_message(
                        msg.number,
                        "❌ No pude vincular ese ID. Asegúrate de que sea un número válido y no esté registrado por otro usuario.",
                    )

            if current_step == "ASK_PORTFOLIO_PREFS":
                choice = msg.text.strip().upper()
                has_fx = "FX" in choice or "AMBOS" in choice or "BOTH" in choice
                has_stocks = "STOCK" in choice or "AMBOS" in choice or "BOTH" in choice

                # Update User
                await client.patch(
                    f"{CORE_SERVICE_URL}/users/{msg.number}",
                    json={
                        "has_fx_portfolio": has_fx,
                        "has_stock_portfolio": has_stocks,
                    },
                )

                # Complete Session
                await client.patch(
                    f"{CORE_SERVICE_URL}/signup/session/{msg.number}",
                    json={"step": "COMPLETED", "completed": True},
                )

                return msgs.text_message(
                    msg.number,
                    "🏁 *¡Configuración Completada!*\n\nGracias por tu información. Ahora estás listo para operar.\n\nUsa el comando **ESTRATEGIAS** para ver qué señales están disponibles.",
                )

        return msgs.text_message(
            msg.number, "Lo siento, no entiendo en qué paso estamos."
        )

    async def _handle_list_strategies(self, msg):
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{CORE_SERVICE_URL}/strategies")
            if resp.status_code == 200:
                strategies = resp.json()
                if not strategies:
                    return msgs.text_message(msg.number, "No hay estrategias activas.")

                text = "📊 *Estrategias Disponibles:*\n\nToca el nombre para suscribirte:\n\n"
                # Button titles must be ≤20 chars — use strategy name directly
                options = []
                for s in strategies:
                    text += f"• *{s['name']}*\n  _{s['description']}_\n\n"
                    options.append(s["name"][:20])

                return msgs.buttonReply_Message(
                    msg, options[:3], text.strip(), "Trading Center"
                )
        return msgs.text_message(msg.number, "Error al obtener estrategias.")

    async def _handle_subscribe(self, msg):
        async with httpx.AsyncClient() as client:
            # Extract strategy name from "!SUSCRIBIR NAME" or similar
            parts = msg.text.strip().split()
            if len(parts) < 2:
                return msgs.text_message(
                    msg.number, "Uso: `SUSCRIBIR [NOMBRE_ESTRATEGIA]`"
                )

            strategy_name = parts[1].upper()
            # Need user_id, which we should have fetched in process_request
            # For simplicity here, we'll re-fetch or pass it
            user_resp = await client.get(f"{CORE_SERVICE_URL}/users/{msg.number}")
            user_id = user_resp.json()["id"]

            resp = await client.post(
                f"{CORE_SERVICE_URL}/strategies/{strategy_name}/subscribe",
                params={"user_id": user_id},
            )
            if resp.status_code == 200:
                return msgs.text_message(
                    msg.number, f"✅ Te has suscrito con éxito a *{strategy_name}*."
                )
            return msgs.text_message(
                msg.number, f"No pude suscribirte a {strategy_name}."
            )

    async def _handle_login(self, msg):
        # Redirect to portfolio login handled by core service
        login_url = f"{get_env_var('APP_URL')}/portfolio/login?phone={msg.number}"
        return msgs.text_message(msg.number, f"🔐 *Acceso Seguro*\n\n{login_url}")


bot_service = BotService()
