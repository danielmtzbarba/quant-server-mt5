from fastapi import FastAPI, Request
import uvicorn
from fastapi.responses import PlainTextResponse
from .core.bot_service import bot_service
from .core.config import settings
from .core.trading_notifications import notification_manager
from common_logging import setup_logging
from .infra.whatsapp.message import Message

# Increase detail for the main logger as well
logger = setup_logging("messaging-service", tag="MESSAGING", color="blue")

app = FastAPI(title="Messaging Service", redirect_slashes=False)


@app.get("/health")
async def health_check():
    logger.debug("GET /health")
    return {"status": "healthy"}


@app.get("/webhook")
async def verify_challenge(request: Request):
    logger.info("GET /webhook (Verification)")
    # Safe Identity: Log the first 3 chars of expected token to verify sync
    expected_preview = (
        (settings.WHATSAPP_AUTH_TOKEN[:3] + "...")
        if settings.WHATSAPP_AUTH_TOKEN
        else "NONE"
    )
    logger.debug(f"[WHATSAPP] Expected Token Identity: {expected_preview}")

    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if token == settings.WHATSAPP_AUTH_TOKEN and challenge is not None:
        return PlainTextResponse(challenge)

    # Safe Diagnosis: Do NOT log the token itself for security, just the failure
    logger.warning(
        f"[WHATSAPP] Token Mismatch! Expected identity {expected_preview}, got {token}"
    )
    return PlainTextResponse("Forbidden", status_code=403)


@app.post("/webhook")
async def receive_message(request: Request):
    payload = await request.json()
    msg = Message(payload)
    if msg.is_message:
        logger.info(f"User ➔ Server ({msg.number})")
        await bot_service.process_request(msg)
    elif msg.is_read:
        logger.debug("Read Check ✅")
    return PlainTextResponse("SUCCESS")


@app.post("/send")
async def send_message_api(request: Request):
    payload = await request.json()
    to = payload.get("to")
    logger.info(f"Server ➔ User ({to})")
    text = payload.get("text")
    if to and text:
        from .infra.whatsapp.utils import send_message
        from .infra.whatsapp import msg_types as msgs

        send_message(msgs.text_message(to, text))
        return {"status": "sent"}
    return {"status": "error", "message": "Missing 'to' or 'text'"}


@app.post("/notifications")
async def handle_notification(request: Request):
    payload = await request.json()
    phone = payload.get("phone")
    event_type = payload.get("event")
    data = payload.get("data", {})

    if not phone or not event_type:
        return {"status": "error", "message": "Missing 'phone' or 'event'"}

    await notification_manager.notify(phone, event_type, data)
    return {"status": "success"}


if __name__ == "__main__":
    logger.info("Messaging Service Ready (MAX VERBOSITY) on port 8003")
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="debug")
