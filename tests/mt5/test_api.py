import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_mt5_service():
    with patch("app.api.monitoring.mt5_service") as m:
        yield m


@pytest.fixture
def mock_sync_service():
    with patch("app.api.sync.sync_service") as m:
        yield m


def test_api_health(mock_mt5_service):
    mock_mt5_service.get_terminal_info.return_value = MagicMock(
        _asdict=lambda: {"name": "MT5"}
    )
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_api_sync_status(mock_sync_service):
    mock_sync_service.get_sync_status.return_value = {
        "symbol": "EURUSD",
        "status": "success",
    }
    response = client.get("/sync_status?symbol=EURUSD")
    assert response.status_code == 200
    assert response.json()["symbol"] == "EURUSD"


def test_api_place_order(mock_mt5_service):
    # Note: trading router uses mt5_service from app.services.mt5_service
    with patch("app.api.trading.mt5_service") as mt5_mock:
        mt5_mock.place_order.return_value = MagicMock(
            status="success", retcode=10009, comment="Done", ticket=123, error_code=0
        )
        response = client.post(
            "/api/order", json={"action": "BUY", "symbol": "EURUSD", "volume": 0.1}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["ticket"] == 123
