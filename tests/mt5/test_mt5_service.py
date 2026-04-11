import pytest
from unittest.mock import MagicMock, patch

try:
    from services.mt5_service.app.core.mt5_service import MT5Service
    from services.mt5_service.app.models.schemas import TradeRequest

    HAS_MT5_SERVICE = True
except (ImportError, ModuleNotFoundError):
    HAS_MT5_SERVICE = False

pytestmark = pytest.mark.skipif(
    not HAS_MT5_SERVICE, reason="MetaTrader5 service not available (likely non-Windows)"
)


@pytest.fixture
def mock_mt5():
    # Patch the actual location in the service
    with patch("services.mt5_service.app.core.mt5_service.mt5") as m:
        yield m


def test_mt5_initialize_success(mock_mt5):
    mock_mt5.initialize.return_value = True
    mock_mt5.positions_get.return_value = []

    service = MT5Service()
    assert service.initialize() is True
    mock_mt5.initialize.assert_called_once()


def test_mt5_initialize_fail(mock_mt5):
    mock_mt5.initialize.return_value = False
    mock_mt5.last_error.return_value = (1, "Failed")

    service = MT5Service()
    assert service.initialize() is False


def test_place_order_buy(mock_mt5):
    mock_mt5.symbol_info_tick.return_value = MagicMock(ask=1.1, bid=1.09)
    mock_mt5.order_send.return_value = MagicMock(
        retcode=10009, comment="Done", order=123
    )
    mock_mt5.TRADE_RETCODE_DONE = 10009

    service = MT5Service()
    trade = TradeRequest(action="BUY", symbol="EURUSD", volume=0.1)
    response = service.place_order(trade)

    assert response.status == "success"
    assert response.ticket == 123
    mock_mt5.order_send.assert_called_once()


def test_place_order_close_fail_no_pos(mock_mt5):
    mock_mt5.positions_get.return_value = None

    service = MT5Service()
    trade = TradeRequest(action="CLOSE", ticket=999)
    response = service.place_order(trade)

    assert response.status == "failed"
    assert "not found" in response.comment
