import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from asset_paths import SETTINGS_FILE


DEFAULT_SETTINGS = {
    "default_export_format": "xlsx",
    "preview_page_size": 100,
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
            return deepcopy(DEFAULT_SETTINGS)
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
        merged = deepcopy(DEFAULT_SETTINGS)
        for key, value in payload.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value
        return merged
