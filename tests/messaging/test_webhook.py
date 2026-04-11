import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

# --- Webhook Handshake (Verification) ---


@pytest.mark.asyncio
async def test_whatsapp_verification_success(msg_client: AsyncClient, mocker):
    """Verify that the WhatsApp verification challenge works."""
    # Mock the auth token in the service settings
    mocker.patch(
        "services.messaging_service.app.main.settings.WHATSAPP_AUTH_TOKEN", "test_token"
    )

    params = {"hub.verify_token": "test_token", "hub.challenge": "123456789"}

    response = await msg_client.get("/webhook", params=params)
    assert response.status_code == 200
    assert response.text == "123456789"


@pytest.mark.asyncio
async def test_whatsapp_verification_forbidden(msg_client: AsyncClient, mocker):
    """Verify that wrong token results in 403."""
    mocker.patch(
        "services.messaging_service.app.main.settings.WHATSAPP_AUTH_TOKEN", "test_token"
    )

    params = {"hub.verify_token": "wrong_token", "hub.challenge": "123456789"}

    response = await msg_client.get("/webhook", params=params)
    assert response.status_code == 403


# --- Incoming Message & Bot Interaction ---


@pytest.mark.asyncio
async def test_incoming_trade_intent(msg_client: AsyncClient, mocker):
    """Verify that an incoming message triggers the OpenAI bot processing."""
    # 1. Mock the internal bot service handler
    mock_process = mocker.patch(
        "services.messaging_service.app.main.bot_service.process_request",
        new_callable=AsyncMock,
    )

    # Simulating a real WhatsApp message payload
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "123456789",
                                    "text": {
                                        "body": "Buy 1.0 unit of EURUSD at market"
                                    },
                                    "id": "msg_123",
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    response = await msg_client.post("/webhook", json=payload)
    assert response.status_code == 200
    assert response.text == "SUCCESS"

    # Verify processing was triggered
    mock_process.assert_called_once()


# --- Internal Signal Notification (Broadcast) ---


@pytest.mark.asyncio
async def test_send_message_api(msg_client: AsyncClient, mocker):
    """Verify that the internal /send API correctly calls the WhatsApp util."""
    # Mock the source since main.py uses a local import
    mock_send = mocker.patch(
        "services.messaging_service.app.infra.whatsapp.utils.send_message",
        return_value={"status": "sent"},
    )

    payload = {"to": "123456789", "text": "Signal Alert: SELL EURUSD"}

    response = await msg_client.post("/send", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "sent"

    # 2. Assert correctly formatted message was sent
    mock_send.assert_called_once()
