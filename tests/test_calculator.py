import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from batch_service import BatchProcessor
from calculator_service import CalculatorService
from fastapi.testclient import TestClient
from main import app
from order_parsers import parse_upload
from sku_resolver import DimensionsCatalog


FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures"
client = TestClient(app)


def test_manual_calculation_500001():
    service = CalculatorService()
    result = service.calculate_manual(85, 500001)

    assert result["success"] is True
    assert result["best_carrier"] == "D(20 kg)"
    assert result["best_price"] == 1300
    assert result["zones"]["delhivery_zone"] == "C2"


def test_dimensions_catalog_direct_and_alias_lookup():
    catalog = DimensionsCatalog(cleanup_suffixes=["__WH", "_WH", "-R1", "_"])

    direct = catalog.resolve(["SR-CLM-T"])
    assert direct.matched is True
    assert direct.mtp_sku == "SR-CLM-T"
    assert direct.weight_kg == 30.0

    child_alias = catalog.resolve(["SR-CLM-TM"])
    assert child_alias.matched is True
    assert child_alias.mtp_sku == "SR-CLM-T"
    assert child_alias.matched_by == "alias:child_sku"

    ul_alias = catalog.resolve(["FVSGSR11BM51569"])
    assert ul_alias.matched is True
    assert ul_alias.mtp_sku == "SR-CLM-T"
    assert ul_alias.matched_by == "alias:ul"


def test_parse_amazon_all_orders():
    sample_file = FIXTURE_ROOT / "amazon_all_orders_sample.txt"
    parsed = parse_upload(sample_file.name, sample_file.read_bytes())

    assert parsed.parser_key == "amazon_all_orders"
    assert parsed.source_platform == "Amazon"
    assert parsed.rows[0]["sku"] == "SR-CLM-TM"
    assert parsed.rows[0]["pincode"] == "142022"


def test_batch_processor_recovers_aliases_from_sample_files():
    calculator = CalculatorService()
    catalog = DimensionsCatalog(cleanup_suffixes=["__WH", "_WH", "-R1", "_R1", "-CL", "_"])
    processor = BatchProcessor(calculator, catalog)

    amazon_sample = (FIXTURE_ROOT / "amazon_all_orders_sample.txt").read_bytes()
    ul_sample = (FIXTURE_ROOT / "urban_ladder_sample.csv").read_bytes()

    result = processor.process_uploads(
        [
            {"name": "amazon-sample.txt", "content": amazon_sample},
            {"name": "urban-ladder-sample.csv", "content": ul_sample},
        ]
    )

    assert result["summary"]["total_files"] == 2
    assert result["summary"]["total_rows"] > 0
    assert result["summary"]["successful_rows"] > 0

    first_success = next(row for row in result["rows"] if not row["exception_reason"])
    assert first_success["resolved_mtp_sku"] != ""
    assert first_success["best_carrier"] != ""


def test_api_job_runs_async_and_completes():
    sample_file = FIXTURE_ROOT / "amazon_all_orders_sample.txt"
    response = client.post(
        "/api/jobs",
        files={"files": (sample_file.name, sample_file.read_bytes(), "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"completed", "processing"}

    job_id = payload["job_id"]
    if payload["status"] == "processing":
        for _ in range(20):
            status_response = client.get(f"/api/jobs/{job_id}")
            status_payload = status_response.json()
            if status_payload["status"] == "completed":
                break
            time.sleep(0.1)
        else:
            raise AssertionError("Async batch job did not complete in time")

    rows_response = client.get(f"/api/jobs/{job_id}/rows?page=1&page_size=10")
    rows_payload = rows_response.json()
    assert rows_payload["status"] == "completed"
    assert rows_payload["total_rows"] > 0
