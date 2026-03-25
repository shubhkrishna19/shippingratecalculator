from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "dist" / "appsail_deploy"
VENDOR_DIR = BUILD_DIR / "vendor"
PIP_PLATFORM_ARGS = [
    "--platform",
    "manylinux2014_x86_64",
    "--implementation",
    "cp",
    "--python-version",
    "39",
    "--only-binary=:all:",
]

FILES_TO_COPY = [
    "app.py",
    "appsail_main.py",
    "asset_paths.py",
    "asset_sync.py",
    "batch_service.py",
    "calculator_service.py",
    "job_store.py",
    "main.py",
    "order_hub_client.py",
    "order_parsers.py",
    "pincodes.csv",
    "price shared.xlsx",
    "Dimensions Master.xlsx",
    "rate_calculator.py",
    "requirements.txt",
    "settings_store.py",
    "SKU Aliases, Parent & Child Master Data (1).xlsx",
    "sku_resolver.py",
]

TREE_TO_COPY = [
    "static",
]


def package_appsail_bundle() -> Path:
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    for relative_path in FILES_TO_COPY:
        source = ROOT / relative_path
        if not source.exists():
            raise FileNotFoundError(f"Missing required AppSail asset: {source}")
        destination = BUILD_DIR / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    for relative_path in TREE_TO_COPY:
        source = ROOT / relative_path
        if not source.exists():
            raise FileNotFoundError(f"Missing required AppSail asset: {source}")
        destination = BUILD_DIR / relative_path
        shutil.copytree(source, destination)

    optional_files = [ROOT / "app_settings.json"]
    for source in optional_files:
        if source.exists():
            shutil.copy2(source, BUILD_DIR / source.name)

    _install_vendor_dependencies()

    return BUILD_DIR


def _install_vendor_dependencies() -> None:
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(VENDOR_DIR),
        *PIP_PLATFORM_ARGS,
        "-r",
        str(ROOT / "requirements.txt"),
    ]
    subprocess.run(command, check=True)


def main() -> None:
    build_dir = package_appsail_bundle()
    print(f"AppSail bundle ready at {build_dir}")


if __name__ == "__main__":
    main()
