import os
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
APP_STATE_ROOT = PROJECT_ROOT
if os.environ.get("VERCEL") == "1":
    APP_STATE_ROOT = Path(tempfile.gettempdir()) / "shipping-rate-calculator"

PRICE_WORKBOOK = PROJECT_ROOT / "price shared.xlsx"
PINCODES_CSV = PROJECT_ROOT / "pincodes.csv"
DIMENSIONS_WORKBOOK = PROJECT_ROOT / "Dimensions Master.xlsx"
SKU_ALIAS_WORKBOOK = PROJECT_ROOT / "SKU Aliases, Parent & Child Master Data (1).xlsx"
SETTINGS_FILE = APP_STATE_ROOT / "app_settings.json"
RUNTIME_DIR = APP_STATE_ROOT / ".runtime"
JOB_DIR = RUNTIME_DIR / "jobs"
STATIC_DIR = PROJECT_ROOT / "static"


def ensure_runtime_dirs() -> None:
    APP_STATE_ROOT.mkdir(parents=True, exist_ok=True)
    JOB_DIR.mkdir(parents=True, exist_ok=True)
