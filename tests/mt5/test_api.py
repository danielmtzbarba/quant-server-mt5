import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# --- MT5 Import Handling ---
try:
    from services.mt5_service.app.main import app as mt5_app

    HAS_MT5_APP = True
except (ImportError, ModuleNotFoundError):
    HAS_MT5_APP = False

try:
    from services.sync_service.app.main import app as sync_app

    HAS_SYNC_APP = True
except (ImportError, ModuleNotFoundError):
    HAS_SYNC_APP = False

# The test client needs a single app. Since the original test combined them,
# and now they are separate, we might need separate clients or a combined app.
# For simplicity, I'll create two clients.
if HAS_MT5_APP:
    mt5_client = TestClient(mt5_app)
else:
    mt5_client = None

if HAS_SYNC_APP:
    sync_client = TestClient(sync_app)
else:
    sync_client = None


@pytest.fixture
def mock_mt5_service():
    # Patch the location in the monitoring router
    with patch("services.mt5_service.app.api.monitoring.mt5_service") as m:
        yield m


@pytest.fixture
def mock_sync_service():
    # Patch where it's imported in the sync router
    with patch("services.sync_service.app.api.sync.sync_service") as m:
        yield m


@pytest.mark.skipif(not HAS_MT5_APP, reason="MT5 Service App not importable")
def test_api_health(mock_mt5_service):
    mock_mt5_service.get_terminal_info.return_value = MagicMock(
        _asdict=lambda: {"name": "MT5"}
    )
    response = mt5_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.skipif(not HAS_SYNC_APP, reason="Sync Service App not importable")
def test_api_sync_status(mock_sync_service):
    mock_sync_service.get_sync_status.return_value = {
        "symbol": "EURUSD",
        "status": "success",
    }
    response = sync_client.get("/sync_status?symbol=EURUSD")
    assert response.status_code == 200
    assert response.json()["symbol"] == "EURUSD"


@pytest.mark.skipif(not HAS_MT5_APP, reason="MT5 Service App not importable")
def test_api_place_order(mock_mt5_service):
    # Note: trading router uses mt5_service from mt5_service.py
    # We patch it at the call site in the router
    with patch("services.mt5_service.app.api.trading.mt5_service") as mt5_mock:
        mt5_mock.place_order.return_value = MagicMock(
            status="success", retcode=10009, comment="Done", ticket=123, error_code=0
        )
        response = mt5_client.post(
            "/api/order", json={"action": "BUY", "symbol": "EURUSD", "volume": 0.1}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["ticket"] == 123
