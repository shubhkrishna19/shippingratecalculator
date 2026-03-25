from __future__ import annotations

import csv
import io
from typing import Any, Optional, Tuple

from openpyxl import Workbook

from calculator_service import CalculatorService
from order_parsers import parse_upload
from sku_resolver import DimensionsCatalog


EXPORT_COLUMNS = [
    "source_platform",
    "source_file",
    "order_id",
    "order_item_id",
    "sku",
    "resolved_mtp_sku",
    "resolved_mtp_name",
    "product_name",
    "quantity",
    "order_status",
    "order_date",
    "dispatch_by_date",
    "promised_delivery_date",
    "ship_service_level",
    "customer_name",
    "ship_to_name",
    "address_line_1",
    "address_line_2",
    "address_line_3",
    "city",
    "state",
    "pincode",
    "phone",
    "email",
    "item_value",
    "currency",
    "resolved_weight_kg",
    "best_carrier",
    "best_rate",
    "zone",
    "exception_reason",
]


class BatchProcessor:
    def __init__(self, calculator: CalculatorService, catalog: DimensionsCatalog) -> None:
        self.calculator = calculator
        self.catalog = catalog

    def process_rows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        enriched_rows: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        duplicates = 0

        for row in rows:
            dedupe_key = self._dedupe_key(row)
            if dedupe_key in seen_keys:
                duplicates += 1
                continue
            seen_keys.add(dedupe_key)
            enriched_rows.append(self._enrich_row(dict(row), row_id=len(enriched_rows)))

        summary = {
            "total_files": 1,
            "total_rows": len(enriched_rows),
            "duplicate_rows_skipped": duplicates,
            "exception_rows": sum(1 for row in enriched_rows if row["exception_reason"]),
            "successful_rows": sum(1 for row in enriched_rows if not row["exception_reason"]),
            "files": [
                {
                    "file_name": "zoho-ssot",
                    "platform": "Zoho SSOT",
                    "parser_key": "order_hub",
                    "rows_found": len(rows),
                }
            ],
        }
        return {"summary": summary, "rows": enriched_rows}

    def process_uploads(self, uploads: list[dict[str, Any]]) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        files_summary: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        duplicates = 0

        for upload in uploads:
            parsed = parse_upload(upload["name"], upload["content"])
            files_summary.append(
                {
                    "file_name": upload["name"],
                    "platform": parsed.source_platform,
                    "parser_key": parsed.parser_key,
                    "rows_found": len(parsed.rows),
                }
            )

            for row in parsed.rows:
                dedupe_key = self._dedupe_key(row)
                if dedupe_key in seen_keys:
                    duplicates += 1
                    continue
                seen_keys.add(dedupe_key)
                rows.append(self._enrich_row(row, row_id=len(rows)))

        summary = {
            "total_files": len(uploads),
            "total_rows": len(rows),
            "duplicate_rows_skipped": duplicates,
            "exception_rows": sum(1 for row in rows if row["exception_reason"]),
            "successful_rows": sum(1 for row in rows if not row["exception_reason"]),
            "files": files_summary,
        }
        return {"summary": summary, "rows": rows}

    def refresh_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["exception_reason"] = ""
        effective_weight = self._effective_weight(row)
        pincode = self._valid_pincode(row.get("pincode", ""))

        if effective_weight is None or effective_weight <= 0:
            row["best_carrier"] = ""
            row["best_rate"] = None
            row["zone"] = ""
            row["carrier_prices"] = {}
            row["zones"] = {}
            row["exception_reason"] = "Weight is missing or invalid."
            return row

        if not pincode:
            row["best_carrier"] = ""
            row["best_rate"] = None
            row["zone"] = ""
            row["carrier_prices"] = {}
            row["zones"] = {}
            row["exception_reason"] = "Pincode is missing or invalid."
            return row

        calculation = self.calculator.calculate_manual(effective_weight, pincode)
        if not calculation.get("success"):
            row["best_carrier"] = ""
            row["best_rate"] = None
            row["zone"] = ""
            row["carrier_prices"] = {}
            row["zones"] = {}
            row["exception_reason"] = calculation.get("error") or "Calculation failed."
            return row

        row["carrier_prices"] = calculation["rates"]
        row["zones"] = calculation["zones"]
        recommended_carrier = row.get("selected_carrier") or calculation["best_carrier"]
        selected_carrier, selected_rate, selected_zone = self._apply_selected_carrier(
            recommended_carrier,
            calculation["rates"],
            calculation["zones"],
        )
        row["selected_carrier"] = selected_carrier
        row["best_carrier"] = selected_carrier
        row["best_rate"] = selected_rate
        row["zone"] = selected_zone
        return row

    def update_row(
        self,
        row: dict[str, Any],
        *,
        weight_kg: Optional[float] = None,
        carrier: Optional[str] = None,
    ) -> dict[str, Any]:
        if weight_kg is not None:
            row["manual_weight_kg"] = round(weight_kg, 3)
            row["resolved_weight_kg"] = round(weight_kg, 3)
        if carrier is not None:
            row["selected_carrier"] = carrier
        return self.refresh_row(row)

    def export_rows(self, rows: list[dict[str, Any]], export_format: str) -> tuple[bytes, str]:
        ordered = self._ordered_rows(rows)
        if export_format == "csv":
            return self._export_csv(ordered), "text/csv"
        return self._export_xlsx(ordered), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def _enrich_row(self, row: dict[str, Any], row_id: int) -> dict[str, Any]:
        resolution = self.catalog.resolve(row["lookup_candidates"])
        quantity = max(int(row.get("quantity") or 1), 1)
        resolved_weight_kg = round((resolution.weight_kg or 0) * quantity, 3) if resolution.matched else None
        pincode = self._valid_pincode(row.get("pincode", ""))

        enriched = {
            **row,
            "row_id": row_id,
            "resolved_mtp_sku": resolution.mtp_sku or "",
            "resolved_mtp_name": resolution.mtp_name or "",
            "matched_by": resolution.matched_by or "",
            "candidate_used": resolution.candidate_used or "",
            "manual_weight_kg": None,
            "resolved_weight_kg": resolved_weight_kg,
            "best_carrier": "",
            "best_rate": None,
            "zone": "",
            "selected_carrier": "",
            "carrier_prices": {},
            "zones": {},
            "exception_reason": "",
        }

        if not resolution.matched:
            enriched["exception_reason"] = resolution.detail or "No matching SKU found in dimensions master."
            return enriched

        if not pincode:
            enriched["exception_reason"] = "Pincode is missing or invalid."
            return enriched

        return self.refresh_row(enriched)

    @staticmethod
    def _dedupe_key(row: dict[str, Any]) -> str:
        return "::".join(
            [
                row["source_platform"],
                row.get("order_id", ""),
                row.get("order_item_id", ""),
                row.get("sku", ""),
                row.get("pincode", ""),
            ]
        )

    @staticmethod
    def _valid_pincode(raw_pincode: str) -> Optional[int]:
        digits = "".join(ch for ch in str(raw_pincode or "") if ch.isdigit())
        if len(digits) != 6:
            return None
        return int(digits)

    @staticmethod
    def _effective_weight(row: dict[str, Any]) -> Optional[float]:
        manual = row.get("manual_weight_kg")
        if manual is not None:
            return float(manual)
        resolved = row.get("resolved_weight_kg")
        return float(resolved) if resolved not in (None, "") else None

    @staticmethod
    def _selected_zone_for_carrier(carrier: str, zones: dict[str, Any]) -> str:
        if carrier == "Affinity":
            return zones.get("affinity_zone") or ""
        if carrier == "Bluedart":
            return zones.get("bluedart_zone") or ""
        return zones.get("delhivery_zone") or ""

    def _apply_selected_carrier(
        self,
        carrier: str,
        rates: dict[str, Any],
        zones: dict[str, Any],
    ) -> Tuple[str, Optional[float], str]:
        if carrier and carrier in rates and rates[carrier] is not None:
            return carrier, rates[carrier], self._selected_zone_for_carrier(carrier, zones)

        available_carriers = [name for name, value in rates.items() if value is not None]
        if not available_carriers:
            return "", None, ""

        best_carrier = min(available_carriers, key=rates.get)
        return best_carrier, rates[best_carrier], self._selected_zone_for_carrier(best_carrier, zones)

    @staticmethod
    def _ordered_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        successful = [row for row in rows if not row["exception_reason"]]
        exceptions = [row for row in rows if row["exception_reason"]]
        return successful + exceptions

    @staticmethod
    def _export_csv(rows: list[dict[str, Any]]) -> bytes:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in EXPORT_COLUMNS})
        return buffer.getvalue().encode("utf-8-sig")

    @staticmethod
    def _export_xlsx(rows: list[dict[str, Any]]) -> bytes:
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Shipping Allocation")
        sheet.append(EXPORT_COLUMNS)
        for row in rows:
            sheet.append([row.get(column, "") for column in EXPORT_COLUMNS])

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()
