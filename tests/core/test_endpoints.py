import pytest
from httpx import AsyncClient


# Test User Endpoints
@pytest.mark.asyncio
async def test_create_get_user(core_client: AsyncClient):
    # Unique phone for every run (using function scope DB)
    phone = "123456789_unique"
    name = "Test User Unique"

    # 1. Create
    response = await core_client.post(
        "/users", params={"phone_number": phone, "name": name}
    )
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["phone_number"] == phone

    # 2. Fetch
    response = await core_client.get(f"/users/{phone}")
    assert response.status_code == 200
    assert response.json()["id"] == user_data["id"]


@pytest.mark.asyncio
async def test_get_user_not_found(core_client: AsyncClient):
    response = await core_client.get("/users/non_existent_666")
    assert response.status_code == 404


# Test Watchlist Endpoints
@pytest.mark.asyncio
async def test_watchlist_lifecycle(core_client: AsyncClient):
    # 1. User First
    phone = "999_wl"
    user_resp = await core_client.post(
        "/users", params={"phone_number": phone, "name": "WL Tester"}
    )
    assert user_resp.status_code == 200
    user_id = user_resp.json()["id"]

    # 2. Add
    response = await core_client.post(
        "/watchlist", params={"user_id": user_id, "symbol": "AAPL", "market": "STOCK"}
    )
    assert response.status_code == 200
    assert response.json().get("success") is True

    # 3. List
    response = await core_client.get(f"/watchlist/{user_id}")
    assert response.status_code == 200
    watchlist = response.json()
    assert any(symbol == "AAPL" for symbol in watchlist)

    # 4. Remove
    response = await core_client.request(
        "DELETE", "/watchlist", params={"user_id": user_id, "symbol": "AAPL"}
    )
    assert response.status_code == 200
    assert response.json().get("success") is True


# Test Alert Endpoints
@pytest.mark.asyncio
async def test_alert_lifecycle(core_client: AsyncClient):
    # 1. User
    phone = "888_alert"
    user_resp = await core_client.post(
        "/users", params={"phone_number": phone, "name": "Alert Tester"}
    )
    assert user_resp.status_code == 200
    user_id = user_resp.json()["id"]

    # 2. Alert
    # Using 'price' as query param (matches main.py), internally maps to target_price
    response = await core_client.post(
        "/alerts",
        params={
            "user_id": user_id,
            "symbol": "BTCUSD",
            "price": 60000.0,
            "condition": ">",
        },
    )
    assert response.status_code == 200
    alert_id = response.json().get("id")
    assert alert_id is not None

    # 3. Fetch
    response = await core_client.get(f"/alerts/{user_id}")
    assert response.status_code == 200
    assert any(alert["id"] == alert_id for alert in response.json())

    # 4. Delete
    response = await core_client.delete(
        f"/alerts/{alert_id}", params={"user_id": user_id}
    )
    assert response.status_code == 200
    assert response.json().get("success") is True
