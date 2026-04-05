import pytest
from httpx import AsyncClient, Response

# --- Improved Trade Gating Logic Tests ---


@pytest.mark.asyncio
async def test_trade_gating_max_positions(exec_client: AsyncClient, mocker):
    """Verify that trades are BLOCKED when MAX_POSITIONS is reached."""
    # 1. Force MAX_POSITIONS to 5 for this test (Avoid module-level uncertainty)
    mocker.patch("services.trading_service.MAX_POSITIONS", 5)

    # 2. Mock the internal AsyncClient in trading_service specifically
    import httpx
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__.return_value = mock_client
    
    async def gating_side_effect(url, **kwargs):
        if "positions/active/count" in str(url):
            return Response(200, json={"count": 5})  # Equal to Max
        return Response(200, json={"status": "success"})

    mock_client.get.side_effect = gating_side_effect
    
    mocker.patch("services.trading_service.httpx.AsyncClient", return_value=mock_client)

    # 3. Attempt to send a signal
    signal_payload = {
        "symbol": "EURUSD",
        "action": "BUY",
        "price": 1.0850,
        "time": "2024-04-05T12:00:00",
    }

    response = await exec_client.post("/signal", json=signal_payload)

    # 4. Assert that the request was GATED (429 Status)
    assert response.status_code == 429
    assert "limit reached" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_signal_broadcast_success(exec_client: AsyncClient, mocker):
    """Verify that a signal is accepted when under the limit."""
    mocker.patch("services.trading_service.MAX_POSITIONS", 5)

    import httpx
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__.return_value = mock_client

    async def success_side_effect(url, **kwargs):
        if "positions/active/count" in str(url):
            return Response(200, json={"count": 2})  # Under limit
        return Response(200, json={"status": "success"})

    mock_client.get.side_effect = success_side_effect
    mock_client.post.return_value = Response(200, json={"status": "success"})

    mocker.patch("services.trading_service.httpx.AsyncClient", return_value=mock_client)

    signal_payload = {
        "symbol": "GBPUSD",
        "action": "SELL",
        "price": 1.2650,
        "time": "2024-04-05T12:05:00",
    }

    response = await exec_client.post("/signal", json=signal_payload)
    assert response.status_code == 200
    # Detail is "QUEUED" by default in success flow
    assert "QUEUED" in response.json().get("detail", "")


# --- MT5 Interaction Tests ---


@pytest.mark.asyncio
async def test_mt5_poll_flow(exec_client: AsyncClient):
    """Verify that the MT5 EA can correctly poll for commands."""
    from services.trading_service import trading_service

    # Clear queue
    while True:
        cmd = trading_service.get_next_mt5_command()
        if not cmd or cmd.get("action") == "NONE":
            break

    # 1. Queue a manual command
    trading_service.queue_mt5_command("BUY", ticket=123, symbol="US30", volume=0.1)

    # 2. Poll the endpoint
    response = await exec_client.get("/poll")
    assert response.status_code == 200
    assert response.json()["action"] == "BUY"

    # 3. Poll again (should be empty)
    response = await exec_client.get("/poll")
    assert response.json()["action"] == "NONE"
