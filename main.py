from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from asset_paths import (
    DIMENSIONS_WORKBOOK,
    PRICE_WORKBOOK,
    SKU_ALIAS_WORKBOOK,
    STATIC_DIR,
)
from asset_sync import export_pincodes_from_workbook, export_rate_calculator_from_workbook
from batch_service import BatchProcessor
from calculator_service import CalculatorService
from job_store import JobStore
from order_hub_client import OrderHubClient
from settings_store import SettingsStore
from sku_resolver import DimensionsCatalog


app = FastAPI(
    title="Shipping Rate Calculator",
    description="Manual calculator and batch allocation workflow for shipping orders.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

settings_store = SettingsStore()
settings = settings_store.load()
calculator = CalculatorService()
catalog = DimensionsCatalog(cleanup_suffixes=settings["sku_cleanup_suffixes"])
processor = BatchProcessor(calculator, catalog)
job_store = JobStore(processor)
RUN_BATCH_IN_BACKGROUND = "X_ZOHO_CATALYST_LISTEN_PORT" in os.environ
STATELESS_BATCH_MODE = os.environ.get("VERCEL") == "1"


class ManualCalculationRequest(BaseModel):
    weight: float = Field(..., gt=0)
    pincode: int = Field(..., ge=100000, le=999999)


class SettingsUpdateRequest(BaseModel):
    default_export_format: str = Field(pattern="^(csv|xlsx)$")
    preview_page_size: int = Field(ge=25, le=500)
    order_hub_base_url: str = ""
    sku_cleanup_suffixes: list[str]


class RowUpdateRequest(BaseModel):
    weight_kg: Optional[float] = Field(default=None, gt=0)
    carrier: Optional[str] = None


class BulkCarrierUpdateRequest(BaseModel):
    mtp_sku: str
    carrier: str


class ClientRowUpdateRequest(BaseModel):
    row: dict[str, Any]
    weight_kg: Optional[float] = Field(default=None, gt=0)
    carrier: Optional[str] = None


class ClientExportRequest(BaseModel):
    rows: list[dict[str, Any]]
    export_format: str = Field(pattern="^(csv|xlsx)$")


class JobWritebackRequest(BaseModel):
    export_format: str = Field(pattern="^(csv|xlsx)$")


class SsotLoadRequest(BaseModel):
    limit: int = Field(default=250, ge=1, le=2000)
    statuses: list[str] = []


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "pincodes_loaded": len(calculator.pincodes),
        "dimensions_rows": len(catalog.dimensions),
        "alias_maps_loaded": {name: len(values) for name, values in catalog.alias_maps.items()},
        "order_hub_configured": bool(settings_store.load().get("order_hub_base_url")),
    }


@app.post("/api/calculate")
def calculate_manual(payload: ManualCalculationRequest) -> dict[str, Any]:
    result = calculator.calculate_manual(payload.weight, payload.pincode)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Calculation failed"))
    return result


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    runtime_settings = settings_store.load()
    return {
        "settings": runtime_settings,
        "assets": {
            "price_workbook": _asset_info(PRICE_WORKBOOK),
            "dimensions_workbook": _asset_info(DIMENSIONS_WORKBOOK),
            "sku_alias_workbook": _asset_info(SKU_ALIAS_WORKBOOK),
        },
    }


@app.put("/api/settings")
def update_settings(payload: SettingsUpdateRequest) -> dict[str, Any]:
    saved = settings_store.save(payload.model_dump())
    catalog.reload(cleanup_suffixes=saved["sku_cleanup_suffixes"])
    return {"settings": saved}


@app.post("/api/settings/assets")
async def upload_asset(
    asset_type: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if os.environ.get("VERCEL") == "1":
        raise HTTPException(
            status_code=501,
            detail="Asset replacement is not supported on Vercel preview deployments.",
        )

    target = _target_asset_path(asset_type)
    if target is None:
        raise HTTPException(status_code=400, detail=f"Unsupported asset type: {asset_type}")

    content = await file.read()
    target.write_bytes(content)

    if asset_type == "price_workbook":
        export_rate_calculator_from_workbook()
        export_pincodes_from_workbook()
        calculator.reload()
    if asset_type in {"dimensions_workbook", "sku_alias_workbook"}:
        catalog.reload(cleanup_suffixes=settings_store.load()["sku_cleanup_suffixes"])

    return {"asset_type": asset_type, "file_name": file.filename, "saved_to": str(target.name)}


@app.post("/api/jobs")
async def create_job(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    uploads: list[dict[str, Any]] = []
    for file in files:
        uploads.append({"name": file.filename, "content": await file.read()})

    if not uploads:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    if STATELESS_BATCH_MODE:
        try:
            processed = processor.process_uploads(uploads)
        except Exception as exc:  # pragma: no cover - surfaced through API response
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "job_mode": "client",
            "job_id": None,
            "status": "completed",
            "error": "",
            "summary": processed["summary"],
            "rows": [_public_row(row) for row in processed["rows"]],
        }

    if RUN_BATCH_IN_BACKGROUND:
        job = job_store.start_processing(uploads)
    else:
        try:
            processed = processor.process_uploads(uploads)
        except Exception as exc:  # pragma: no cover - surfaced through API response
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job = job_store.create_completed(processed)

    return {
        "job_mode": "server",
        "job_id": job["job_id"],
        "status": job["status"],
        "error": job.get("error", ""),
        "summary": job["summary"],
    }


@app.post("/api/jobs/ssot")
def create_ssot_job(payload: SsotLoadRequest) -> dict[str, Any]:
    client = _get_order_hub_client()
    try:
        source_rows = client.fetch_shipping_orders(limit=payload.limit, statuses=payload.statuses)
        processed = processor.process_rows(source_rows["rows"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if STATELESS_BATCH_MODE:
        return {
            "job_mode": "client",
            "job_id": None,
            "status": "completed",
            "error": "",
            "summary": processed["summary"],
            "rows": [_public_row(row) for row in processed["rows"]],
        }

    job = job_store.create_completed(processed)
    return {
        "job_mode": "server",
        "job_id": job["job_id"],
        "status": job["status"],
        "error": job.get("error", ""),
        "summary": job["summary"],
    }


@app.post("/api/rows/recalculate")
def recalculate_client_row(payload: ClientRowUpdateRequest) -> dict[str, Any]:
    updated = processor.update_row(
        dict(payload.row),
        weight_kg=payload.weight_kg,
        carrier=payload.carrier,
    )
    return _public_row(updated)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    try:
        job = job_store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    return {
        "job_id": job_id,
        "status": job["status"],
        "error": job.get("error", ""),
        "summary": job["summary"],
    }


@app.get("/api/jobs/{job_id}/rows")
def get_job_rows(job_id: str, page: int = 1, page_size: int = 100) -> dict[str, Any]:
    try:
        return job_store.get_page(job_id, page=page, page_size=page_size)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.patch("/api/jobs/{job_id}/rows/{row_id}")
def update_job_row(job_id: str, row_id: int, payload: RowUpdateRequest) -> dict[str, Any]:
    try:
        row = job_store.update_row(job_id, row_id, weight_kg=payload.weight_kg, carrier=payload.carrier)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return row


@app.post("/api/jobs/{job_id}/bulk-carrier")
def bulk_update_carrier(job_id: str, payload: BulkCarrierUpdateRequest) -> dict[str, Any]:
    try:
        result = job_store.bulk_apply_carrier(job_id, payload.mtp_sku, payload.carrier)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result


@app.get("/api/jobs/{job_id}/export")
def export_job(job_id: str, export_format: str = "xlsx") -> Response:
    if export_format not in {"csv", "xlsx"}:
        raise HTTPException(status_code=400, detail="Unsupported export format.")

    try:
        content, media_type = job_store.export(job_id, export_format)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    filename = f"shipping-allocation-{job_id}.{export_format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@app.post("/api/export")
def export_client_rows(payload: ClientExportRequest) -> Response:
    content, media_type = processor.export_rows(payload.rows, payload.export_format)
    filename = f"shipping-allocation.{payload.export_format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@app.post("/api/jobs/{job_id}/writeback")
def writeback_job(job_id: str, payload: JobWritebackRequest) -> dict[str, Any]:
    client = _get_order_hub_client()
    try:
        job = job_store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="Job is still processing.")
    try:
        return client.writeback_rows(job["rows"], export_format=payload.export_format)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jobs/{job_id}/import-to-ssot")
def import_job_to_ssot(job_id: str, payload: JobWritebackRequest) -> dict[str, Any]:
    client = _get_order_hub_client()
    try:
        job = job_store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="Job is still processing.")
    try:
        return client.import_rows(job["rows"], export_format=payload.export_format)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/writeback")
def writeback_client_rows(payload: ClientExportRequest) -> dict[str, Any]:
    client = _get_order_hub_client()
    try:
        return client.writeback_rows(payload.rows, export_format=payload.export_format)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/import-to-ssot")
def import_client_rows_to_ssot(payload: ClientExportRequest) -> dict[str, Any]:
    client = _get_order_hub_client()
    try:
        return client.import_rows(payload.rows, export_format=payload.export_format)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _asset_info(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"name": path.name, "exists": False}
    stat = path.stat()
    return {
        "name": path.name,
        "exists": True,
        "size_bytes": stat.st_size,
        "updated_at": stat.st_mtime,
    }


def _target_asset_path(asset_type: str) -> Optional[Path]:
    return {
        "price_workbook": PRICE_WORKBOOK,
        "dimensions_workbook": DIMENSIONS_WORKBOOK,
        "sku_alias_workbook": SKU_ALIAS_WORKBOOK,
    }.get(asset_type)


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    public = dict(row)
    public.pop("raw_fields", None)
    return public


def _get_order_hub_client() -> OrderHubClient:
    order_hub_base_url = settings_store.load().get("order_hub_base_url", "")
    try:
        return OrderHubClient(order_hub_base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.exception_handler(FileNotFoundError)
def handle_missing_file(_, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})

