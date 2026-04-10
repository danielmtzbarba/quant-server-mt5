import pytest
from unittest.mock import patch
from app.services.sync_service import SyncService


@pytest.fixture
def sync_service():
    with patch("app.services.sync_service.influx_service"):
        yield SyncService()


def test_get_sync_status(sync_service):
    # sync_service is already patched with influx_service mock in the fixture
    with patch(
        "app.services.sync_service.influx_service.get_last_timestamp",
        return_value="2026-01-01T00:00:00Z",
    ):
        status = sync_service.get_sync_status("EURUSD")
        assert status["symbol"] == "EURUSD"
        assert status["last_timestamp"] == "2026-01-01T00:00:00Z"


def test_run_health_check_empty(sync_service):
    with patch(
        "app.services.sync_service.DataHealthMonitor.check_integrity"
    ) as mock_check:
        mock_check.return_value = {"status": "empty", "gaps": []}
        report = sync_service.run_health_check("EURUSD")
        assert report["status"] == "empty"
        assert "EURUSD" in sync_service.repair_flags
        assert sync_service.repair_flags["EURUSD"][0]["start"] == "-14d"


def test_check_repair_no_gaps(sync_service):
    sync_service.repair_flags = {}
    repair = sync_service.check_repair("EURUSD")
    assert repair["repair"] is False
    assert repair["gaps"] == []


def test_check_repair_with_gaps(sync_service):
    from datetime import datetime

    sync_service.repair_flags = {
        "EURUSD": [{"start": datetime(2026, 1, 1), "end": datetime(2026, 1, 2)}]
    }
    repair = sync_service.check_repair("EURUSD")
    assert repair["repair"] is True
    assert repair["gaps"][0]["start"] == "2026-01-01T00:00:00"
