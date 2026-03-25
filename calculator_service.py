import csv
import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

import rate_calculator as rate_calculator_module

from asset_paths import PINCODES_CSV


class CalculatorService:
    def __init__(self) -> None:
        self.module: ModuleType = rate_calculator_module
        self.reload()

    def reload(self) -> None:
        self.module = importlib.reload(self.module)
        self.pincodes = self._load_pincodes(PINCODES_CSV)

    def calculate_manual(self, weight: float, pincode: int) -> dict[str, Any]:
        result = self.module.calculate_best_rate(weight, pincode, self.pincodes)
        if result.get("error"):
            return {"success": False, "error": result["error"]}

        return {
            "success": True,
            "inputs": result["inputs"],
            "zones": result["zone_lookups"],
            "pincode_info": result["pincode_info"],
            "rates": result["carrier_prices"],
            "best_carrier": result["preferred_partner"],
            "best_price": result["minimum_logistics_fee"],
        }

    @staticmethod
    def _load_pincodes(path: Path) -> dict[str, dict[str, Any]]:
        database: dict[str, dict[str, Any]] = {}
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                pincode = str(row.get("Pincode", "")).strip()
                if not pincode:
                    continue
                database[pincode] = {
                    "delhivery_zone": str(row.get("Zone", "")).strip(),
                    "bluedart_zone": str(row.get("BD-Zone", "")).strip(),
                    "state_code": str(row.get("State Code", "")).strip(),
                    "city": str(row.get("City", "")).strip(),
                    "prepaid": str(row.get("Prepaid", "")).strip(),
                    "cod": str(row.get("COD", "")).strip(),
                    "reverse_pickup": str(row.get("Reverse Pickup", "")).strip(),
                    "express_tat": str(row.get("Express TAT", "")).strip(),
                    "surface_tat": str(row.get("Surface TAT", "")).strip(),
                    "bd_state_code": str(row.get("BD-State Code", "")).strip(),
                    "bd_serviceable": str(row.get("BD-serviceable status", "")).strip(),
                }
        return database
