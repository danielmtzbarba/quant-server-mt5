from fastapi import FastAPI, Request
import uvicorn
from fastapi.responses import PlainTextResponse
from services.bot_service import bot_service
from whatsapp.message import Message
import whatsapp as wa
from common_logging import setup_logging
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Messaging Service (DEBUG MODE)...")
    # LIFTING THE MUZZLE: Allow uvicorn to report everything
    yield
    logger.info("Shutting down Messaging Service...")


# Increase detail for the main logger as well
logger = setup_logging("messaging-service", tag="MESSAGING", color="blue")

app = FastAPI(title="Messaging Service", lifespan=lifespan, redirect_slashes=False)


@app.get("/health")
async def health_check():
    logger.debug("GET /health")
    return {"status": "healthy"}


@app.get("/webhook")
async def verify_challenge(request: Request):
    logger.info("GET /webhook (Verification)")
    # Safe Identity: Log the first 3 chars of expected token to verify sync
    expected_preview = (wa.auth_token[:3] + "...") if wa.auth_token else "NONE"
    logger.debug(f"[WHATSAPP] Expected Token Identity: {expected_preview}")

    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if token == wa.auth_token and challenge is not None:
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
        from whatsapp.utils import send_message
        import whatsapp.msg_types as msgs

        send_message(msgs.text_message(to, text))
        return {"status": "sent"}
    return {"status": "error", "message": "Missing 'to' or 'text'"}


if __name__ == "__main__":
    logger.info("Messaging Service Ready (MAX VERBOSITY) on port 8003")
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="debug")
