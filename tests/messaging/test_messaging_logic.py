import pytest
from httpx import AsyncClient, Response


@pytest.mark.asyncio
async def test_receive_whatsapp_message_flow(msg_client: AsyncClient, mocker):
    """Verify that an incoming WhatsApp message triggers the bot flow."""

    # 1. Mock internal AsyncClient in bot_service (Core service check)
    import httpx

    mock_httpx = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_httpx.__aenter__.return_value = mock_httpx
    mock_httpx.get.return_value = Response(
        200, json={"id": 1, "phone_number": "123456789"}
    )
    mocker.patch(
        "services.messaging_service.app.core.bot_service.httpx.AsyncClient",
        return_value=mock_httpx,
    )

    # 2. Mock Agent/AI — patch the lazy singleton to return a mock executor
    mock_executor = mocker.AsyncMock()
    mock_ai_resp = mocker.Mock()
    mock_ai_resp.content = "Sure, I'll help with that."
    mock_executor.ainvoke.return_value = {"messages": [mock_ai_resp]}
    mocker.patch(
        "services.messaging_service.app.core.bot_service.get_agent_executor_singleton",
        return_value=mock_executor,
    )

    # 3. Mock WhatsApp Send
    mock_wa_send = mocker.patch(
        "services.messaging_service.app.core.bot_service.whatsapp_service.send_messages"
    )

    # 4. Mock Message payload construction
    mocker.patch(
        "services.messaging_service.app.main.Message",
        return_value=mocker.Mock(
            is_message=True, number="123456789", text="Hello Bot", id="msg_123"
        ),
    )

    # 5. Call Webhook
    response = await msg_client.post("/webhook", json={"mock": "data"})
    assert response.status_code == 200
    assert response.text == "SUCCESS"

    # 6. Verify flow completion
    assert mock_wa_send.called


@pytest.mark.asyncio
async def test_messaging_send_endpoint(msg_client: AsyncClient, mocker):
    """Verify that the /send endpoint correctly calls the WhatsApp utility."""
    # We patch the source since main.py uses a local import
    mock_send = mocker.patch(
        "services.messaging_service.app.infra.whatsapp.utils.send_message"
    )

    payload = {"to": "123456789", "text": "Hello from Server"}

    response = await msg_client.post("/send", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert mock_send.called
