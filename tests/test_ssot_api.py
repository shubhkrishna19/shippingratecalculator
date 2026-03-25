import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from unittest.mock import Mock

import main
from order_hub_client import OrderHubClient
from settings_store import SettingsStore


class FakeOrderHubClient:
    def __init__(self) -> None:
        self.fetch_calls = []
        self.writeback_calls = []
        self.import_calls = []

    def fetch_shipping_orders(self, limit: int = 250, statuses: list[str] | None = None):
        self.fetch_calls.append({"limit": limit, "statuses": statuses or []})
        return {
            "rows": [
                {
                    "source_file": "zoho_ssot",
                    "source_platform": "Amazon",
                    "parser_key": "order_hub",
                    "source_row_number": 1,
                    "order_id": "AMZ-1001",
                    "order_item_id": "AMZ-1001-1",
                    "sku": "SR-CLM-TM",
                    "quantity": 1,
                    "product_name": "Shelf",
                    "order_status": "Pending",
                    "order_date": "2026-03-16",
                    "customer_name": "Riya Sharma",
                    "ship_to_name": "Riya Sharma",
                    "city": "Hyderabad",
                    "state": "Telangana",
                    "pincode": "500001",
                    "phone": "919900001111",
                    "email": "riya@example.com",
                    "address_line_1": "A-21 Street",
                    "address_line_2": "",
                    "address_line_3": "",
                    "ship_service_level": "",
                    "item_value": 1999,
                    "currency": "INR",
                    "dispatch_by_date": "",
                    "promised_delivery_date": "",
                    "lookup_candidates": ["SR-CLM-TM", "Shelf"],
                    "canonical_order_id": "ord_test",
                    "canonical_line_id": "line_test",
                    "external_key": "Amazon::AMZ-1001::AMZ-1001-1",
                    "raw_fields": {},
                }
            ],
            "count": 1,
        }

    def writeback_rows(self, rows, export_format: str = "xlsx"):
        self.writeback_calls.append({"rows": rows, "export_format": export_format})
        return {
            "mode": "writeback",
            "updated_rows": len(rows),
            "orders_touched": 1,
            "export_batch": {"batch_id": "batch_123"},
            "download_url": "https://orderhub.example.com/api/shipping/export/batch_123",
        }

    def import_rows(self, rows, export_format: str = "xlsx"):
        self.import_calls.append({"rows": rows, "export_format": export_format})
        return {
            "mode": "import",
            "imported_rows": len(rows),
            "updated_rows": 0,
            "orders_touched": 1,
            "export_batch": {"batch_id": "batch_456"},
            "download_url": "https://orderhub.example.com/api/shipping/export/batch_456",
        }


client = TestClient(main.app)


def test_settings_store_uses_order_hub_env_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ORDER_HUB_BASE_URL", "https://orderhub.example.com")
    store = SettingsStore(tmp_path / "app_settings.json")

    loaded = store.load()

    assert loaded["order_hub_base_url"] == "https://orderhub.example.com"


def test_settings_store_uses_order_hub_env_when_file_value_blank(tmp_path, monkeypatch):
    monkeypatch.setenv("ORDER_HUB_BASE_URL", "https://orderhub.example.com")
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(json.dumps({"order_hub_base_url": ""}), encoding="utf-8")
    store = SettingsStore(settings_path)

    loaded = store.load()

    assert loaded["order_hub_base_url"] == "https://orderhub.example.com"


def test_ssot_job_endpoint_uses_order_hub_client(monkeypatch):
    fake = FakeOrderHubClient()
    monkeypatch.setattr(main, "STATELESS_BATCH_MODE", True)
    monkeypatch.setattr(main, "_get_order_hub_client", lambda: fake)

    response = client.post("/api/jobs/ssot", json={"limit": 1, "statuses": ["Pending"]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_mode"] == "client"
    assert payload["status"] == "completed"
    assert payload["summary"]["total_rows"] == 1
    assert payload["rows"][0]["resolved_mtp_sku"] == "SR-CLM-T"
    assert fake.fetch_calls == [{"limit": 1, "statuses": ["Pending"]}]


def test_writeback_endpoint_uses_order_hub_client(monkeypatch):
    fake = FakeOrderHubClient()
    monkeypatch.setattr(main, "_get_order_hub_client", lambda: fake)

    response = client.post(
        "/api/writeback",
        json={
            "rows": [
                {
                    "canonical_order_id": "ord_test",
                    "canonical_line_id": "line_test",
                    "external_key": "Amazon::AMZ-1001::AMZ-1001-1",
                    "source_platform": "Amazon",
                    "order_id": "AMZ-1001",
                    "order_item_id": "AMZ-1001-1",
                    "sku": "SR-CLM-TM",
                    "product_name": "Shelf",
                    "quantity": 1,
                    "resolved_mtp_sku": "SR-CLM-T",
                    "resolved_mtp_name": "Shelf",
                    "resolved_weight_kg": 30.0,
                    "best_carrier": "D(20 kg)",
                    "best_rate": 1300,
                    "zone": "C2",
                    "exception_reason": "",
                }
            ],
            "export_format": "xlsx",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated_rows"] == 1
    assert fake.writeback_calls[0]["export_format"] == "xlsx"
    assert fake.writeback_calls[0]["rows"][0]["canonical_line_id"] == "line_test"


def test_import_endpoint_uses_order_hub_client(monkeypatch):
    fake = FakeOrderHubClient()
    monkeypatch.setattr(main, "_get_order_hub_client", lambda: fake)

    response = client.post(
        "/api/import-to-ssot",
        json={
            "rows": [
                {
                    "source_platform": "Amazon",
                    "order_id": "AMZ-2001",
                    "order_item_id": "AMZ-2001-1",
                    "sku": "SR-CLM-TM",
                    "product_name": "Shelf",
                    "quantity": 1,
                    "resolved_mtp_sku": "SR-CLM-T",
                    "resolved_mtp_name": "Shelf",
                    "resolved_weight_kg": 30.0,
                    "best_carrier": "D(20 kg)",
                    "best_rate": 1300,
                    "zone": "C2",
                    "exception_reason": "",
                }
            ],
            "export_format": "xlsx",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["imported_rows"] == 1
    assert fake.import_calls[0]["export_format"] == "xlsx"
    assert fake.import_calls[0]["rows"][0]["order_id"] == "AMZ-2001"


def test_order_hub_client_empty_response_error_is_clear():
    response = Mock()
    response.raise_for_status.return_value = None
    response.text = ""

    try:
        OrderHubClient._decode_json_response(response, endpoint="/api/shipping/orders")
    except ValueError as exc:
        assert "empty response" in str(exc)
        assert "/api/shipping/orders" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty response")



