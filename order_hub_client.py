from __future__ import annotations

from typing import Any

import requests


class OrderHubClient:
    def __init__(self, base_url: str) -> None:
        normalized = (base_url or "").strip().rstrip("/")
        if not normalized:
            raise ValueError("Order Hub base URL is not configured.")
        self.base_url = normalized

    def fetch_shipping_orders(self, limit: int = 250, statuses: list[str] | None = None) -> dict[str, Any]:
        params = {"limit": limit}
        if statuses:
            params["statuses"] = ",".join(statuses)
        response = requests.get(f"{self.base_url}/api/shipping/orders", params=params, timeout=120)
        response.raise_for_status()
        return response.json()

    def writeback_rows(self, rows: list[dict[str, Any]], export_format: str = "xlsx") -> dict[str, Any]:
        payload_rows = []
        for row in rows:
            payload_rows.append(
                {
                    "canonical_line_id": row.get("canonical_line_id"),
                    "external_key": row.get("external_key"),
                    "source_platform": row.get("source_platform"),
                    "source_order_id": row.get("order_id"),
                    "source_line_id": row.get("order_item_id"),
                    "resolved_mtp_sku": row.get("resolved_mtp_sku"),
                    "resolved_mtp_name": row.get("resolved_mtp_name"),
                    "resolved_weight_kg": row.get("resolved_weight_kg"),
                    "selected_carrier": row.get("best_carrier") or row.get("selected_carrier"),
                    "selected_rate": row.get("best_rate") if row.get("best_rate") is not None else row.get("selected_rate"),
                    "zone": row.get("zone"),
                    "exception_reason": row.get("exception_reason"),
                    "processing_status": "exception" if row.get("exception_reason") else "reviewed",
                    "export_payload": {
                        "canonical_order_id": row.get("canonical_order_id"),
                        "canonical_line_id": row.get("canonical_line_id"),
                        "external_key": row.get("external_key"),
                        "source_platform": row.get("source_platform"),
                        "source_order_id": row.get("order_id"),
                        "source_line_id": row.get("order_item_id"),
                        "sku": row.get("sku"),
                        "product_name": row.get("product_name"),
                        "quantity": row.get("quantity"),
                        "resolved_mtp_sku": row.get("resolved_mtp_sku"),
                        "resolved_mtp_name": row.get("resolved_mtp_name"),
                        "resolved_weight_kg": row.get("resolved_weight_kg"),
                        "selected_carrier": row.get("best_carrier") or row.get("selected_carrier"),
                        "selected_rate": row.get("best_rate") if row.get("best_rate") is not None else row.get("selected_rate"),
                        "zone": row.get("zone"),
                        "exception_reason": row.get("exception_reason"),
                        "processing_status": "exception" if row.get("exception_reason") else "reviewed",
                    },
                }
            )

        response = requests.post(
            f"{self.base_url}/api/shipping/writeback",
            json={
                "rows": payload_rows,
                "export_format": export_format,
                "create_export_batch": True,
                "actor_system": "shipping",
            },
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()
        export_batch = data.get("export_batch") or {}
        if export_batch.get("batch_id"):
            data["download_url"] = f"{self.base_url}/api/shipping/export/{export_batch['batch_id']}"
        data.setdefault("mode", "writeback")
        return data

    def import_rows(self, rows: list[dict[str, Any]], export_format: str = "xlsx") -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/shipping/import",
            json={
                "rows": rows,
                "export_format": export_format,
                "create_export_batch": True,
                "actor_system": "shipping",
                "source_label": "shipping_review_batch",
            },
            timeout=240,
        )
        response.raise_for_status()
        data = response.json()
        export_batch = data.get("export_batch") or {}
        if export_batch.get("batch_id"):
            data["download_url"] = f"{self.base_url}/api/shipping/export/{export_batch['batch_id']}"
        data.setdefault("mode", "import")
        return data

