from fastapi import FastAPI, Request
import uvicorn
import logging
from fastapi.responses import PlainTextResponse
from .core.bot_service import bot_service
from .core.config import settings
from .core.trading_notifications import notification_manager
from common_logging import (
    setup_logging,
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
)
from .infra.whatsapp.message import Message
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter

# Custom metrics
PARSE_FAILURES = Counter(
    "messaging_webhook_parse_failures_total", "Total number of failed webhook parses"
)
OUTBOUND_FAIL_COUNT = Counter(
    "messaging_outbound_send_failures_total", "Total number of failed outbound messages"
)
WEBHOOK_COUNT = Counter(
    "messaging_webhook_received_total",
    "Total number of webhooks received",
    ["event_type"],
)

# Increase detail for the main logger as well
# Setup structured logging
logger = setup_logging("messaging-service")

app = FastAPI(title="Messaging Service", redirect_slashes=False)

# Add structured logging middlewares
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Prometheus instrumentation
Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health_check():
    logger.debug("GET /health")
    return {"status": "healthy"}


@app.get("/webhook")
async def verify_challenge(request: Request):
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("GET /webhook (Verification)")
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
    logger.info("webhook_received", payload=payload)
    msg = Message(payload)

    # Increment webhook counter
    event_label = (
        "message" if msg.is_message else ("status" if msg.status else "unknown")
    )
    WEBHOOK_COUNT.labels(event_type=event_label).inc()

    if msg.is_message:
        logger.info("message_parsed", phone=msg.number, text=msg.text)
        await bot_service.process_request(msg)
    elif msg.is_read:
        logger.debug("message_read_check")
    elif not msg.status:
        # Not a message and not a status update = potential parse failure
        PARSE_FAILURES.inc()

    return PlainTextResponse("SUCCESS")


@app.post("/send")
async def send_message_api(request: Request):
    payload = await request.json()
    to = payload.get("to")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Server ➔ User ({to})")
    text = payload.get("text")
    if to and text:
        from .infra.whatsapp.utils import send_message
        from .infra.whatsapp import msg_types as msgs

        try:
            send_message(msgs.text_message(to, text))
            return {"status": "sent"}
        except Exception as e:
            logger.error("outbound_send_failed", error=str(e))
            OUTBOUND_FAIL_COUNT.inc()
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": "Missing 'to' or 'text'"}


@app.post("/notifications")
async def handle_notification(request: Request):
    payload = await request.json()
    phone = payload.get("phone")
    event_type = payload.get("event")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Event ➔ User ({phone}: {event_type})")
    data = payload.get("data", {})

    if not phone or not event_type:
        return {"status": "error", "message": "Missing 'phone' or 'event'"}

    await notification_manager.notify(phone, event_type, data)
    return {"status": "success"}


if __name__ == "__main__":
    logger.info("Messaging Service Ready on port 8003")
    uvicorn.run(app, host="0.0.0.0", port=8003, log_config=None)
