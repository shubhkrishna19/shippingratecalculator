import json
import os
from pathlib import Path
from typing import Any, Optional

from asset_paths import SETTINGS_FILE


def default_settings() -> dict[str, Any]:
    return {
        "default_export_format": "xlsx",
        "preview_page_size": 100,
        "order_hub_base_url": os.environ.get("ORDER_HUB_BASE_URL", "").strip(),
        "sku_cleanup_suffixes": [
            "__WH",
            "_WH",
            "-R1",
            "_R1",
            "-CL",
            "_CL",
            "_",
        ],
        "asset_files": {
            "price_workbook": "price shared.xlsx",
            "dimensions_workbook": "Dimensions Master.xlsx",
            "sku_alias_workbook": "SKU Aliases, Parent & Child Master Data (1).xlsx",
        },
    }


class SettingsStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or SETTINGS_FILE

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return default_settings()
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return self._merge_defaults(data)

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._merge_defaults(payload)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        return data

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        current = self.load()
        current.update(patch)
        return self.save(current)

    def _merge_defaults(self, payload: dict[str, Any]) -> dict[str, Any]:
        merged = default_settings()
        for key, value in payload.items():
            if key == "order_hub_base_url" and isinstance(value, str) and not value.strip():
                # Keep the runtime env fallback active unless an explicit override URL is saved.
                continue
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value
        return merged

