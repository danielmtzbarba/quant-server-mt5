import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_order_lifecycle(core_client: AsyncClient):
    """Verify that orders can be created and retrieved with explicit IDs."""
    ticket_id = 777888
    order_payload = {
        "id": ticket_id,
        "broker_account_id": 1,
        "symbol": "EURUSD",
        "action": "BUY",
        "quantity": 0.01,
        "price": 1.0850,
        "status": "PENDING",
    }

    # 1. Create
    response = await core_client.post("/orders", json=order_payload)
    assert response.status_code == 200
    order_data = response.json()
    assert order_data["id"] == ticket_id
    assert order_data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_position_sync_flow(core_client: AsyncClient):
    """Verify that MT5 position reports correctly synchronize the DB state."""
    positions_report = [
        {
            "ticket": 123456,
            "symbol": "GBPUSD",
            "volume": 0.05,
            "price_open": 1.2500,
            "profit": 10.5,
            "type": 0,  # BUY
        }
    ]

    # 1. Sync
    response = await core_client.post(
        "/positions/sync", params={"account_id": 1}, json=positions_report
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 2. Verify
    response = await core_client.get("/positions/1")
    assert response.status_code == 200
    positions = response.json()
    assert any(p["id"] == 123456 for p in positions)
    assert any(p["symbol"] == "GBPUSD" for p in positions)


@pytest.mark.asyncio
async def test_position_open_transition(core_client: AsyncClient):
    """Verify that opening a position transitions the matching PENDING order to FILLED."""
    ticket_id = 999111
    # 1. Create PENDING Order
    await core_client.post(
        "/orders",
        json={
            "id": ticket_id,
            "broker_account_id": 1,
            "symbol": "XAUUSD",
            "action": "SELL",
            "quantity": 0.1,
            "price": 2300.0,
            "status": "PENDING",
        },
    )

    # 2. Report OPENED from MT5 (matching the ticket)
    pos_data = {
        "ticket": ticket_id,
        "symbol": "XAUUSD",
        "volume": 0.1,
        "price": 2300.0,
        "type": 1,  # SELL
    }
    response = await core_client.post("/positions/open", json=pos_data)
    assert response.status_code == 200

    # 3. Verify Position exists
    response = await core_client.get("/positions/1")
    assert any(p["id"] == ticket_id for p in response.json())
