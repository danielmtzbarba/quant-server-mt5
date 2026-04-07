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
        if "subscribers" in str(url):
            return Response(
                200,
                json=[
                    {
                        "phone_number": "123456",
                        "broker_accounts": [{"id": 1, "account_number": "DEMO-MT5"}],
                    }
                ],
            )
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
    assert "position limit reached" in response.json().get("detail", "").lower()


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
        if "subscribers" in str(url):
            return Response(
                200,
                json=[
                    {
                        "phone_number": "123456",
                        "name": "Test User",
                        "broker_accounts": [{"id": 1, "account_number": "DEMO-MT5"}],
                    }
                ],
            )
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
    # Detail is "BROADCASTED" in the new multi-tenant flow
    assert "BROADCASTED" in response.json().get("detail", "")


# --- MT5 Interaction Tests ---


@pytest.mark.asyncio
async def test_mt5_direct_execution_flow(exec_client: AsyncClient, mocker):
    """Verify that signals trigger immediate direct HTTP calls to the MT5 Engine."""
    mocker.patch("services.trading_service.MAX_POSITIONS", 5)

    import httpx

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__.return_value = mock_client

    async def execution_side_effect(url, **kwargs):
        # 1. Handle Core Service queries (active count and subscribers)
        if "positions/active/count" in str(url):
            return Response(200, json={"count": 0})
        if "subscribers" in str(url):
            return Response(
                200,
                json=[
                    {
                        "phone_number": "123",
                        "name": "Live Trader",
                        "broker_accounts": [{"id": 1, "account_number": "DEMO-MT5"}],
                    }
                ],
            )
        # 2. Handle the direct MT5 Engine API call (The new Phase 2 logic)
        if "api/order" in str(url):
            return Response(200, json={"status": "success", "ticket": 9999123})

        return Response(200, json={"status": "success"})

    mock_client.get.side_effect = execution_side_effect
    mock_client.post.side_effect = execution_side_effect

    mocker.patch("services.trading_service.httpx.AsyncClient", return_value=mock_client)

    signal_payload = {
        "symbol": "XAUUSD",
        "action": "BUY",
        "price": 2350.50,
        "time": "2024-04-05T12:30:00",
    }

    # Execute the signal endpoint
    response = await exec_client.post("/signal", json=signal_payload)

    assert response.status_code == 200
    assert "BROADCASTED" in response.json().get("detail", "")

    # Verification: Ensure the MT5 Engine API was actually called once
    called_urls = [str(call[0][0]) for call in mock_client.post.call_args_list]
    assert any("api/order" in url for url in called_urls)
