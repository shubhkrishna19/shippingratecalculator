from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from asset_paths import JOB_DIR, ensure_runtime_dirs
from batch_service import BatchProcessor


class JobStore:
    def __init__(self, processor: BatchProcessor) -> None:
        self.processor = processor
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        ensure_runtime_dirs()

    def create_completed(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "error": "",
                "summary": payload["summary"],
                "rows": payload["rows"],
            }
            self._jobs[job_id] = job
            self._persist(job_id)
            return job

    def start_processing(self, uploads: list[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "processing",
                "error": "",
                "summary": {
                    "total_files": len(uploads),
                    "total_rows": 0,
                    "duplicate_rows_skipped": 0,
                    "exception_rows": 0,
                    "successful_rows": 0,
                    "files": [],
                },
                "rows": [],
            }
            self._jobs[job_id] = job
            self._persist(job_id)

        worker = threading.Thread(target=self._process_job, args=(job_id, uploads), daemon=True)
        worker.start()
        return job

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            if job_id in self._jobs:
                return self._jobs[job_id]
            path = JOB_DIR / f"{job_id}.json"
            if not path.exists():
                raise KeyError(job_id)
            job = json.loads(path.read_text(encoding="utf-8"))
            self._jobs[job_id] = job
            return job

    def get_page(self, job_id: str, page: int, page_size: int) -> dict[str, Any]:
        job = self.get(job_id)
        if job["status"] != "completed":
            return {
                "rows": [],
                "total_rows": 0,
                "page": 1,
                "page_size": page_size,
                "total_pages": 1,
                "status": job["status"],
                "error": job.get("error", ""),
            }

        rows = job["rows"]
        start = max(page - 1, 0) * page_size
        end = start + page_size
        return {
            "rows": [self._public_row(row) for row in rows[start:end]],
            "total_rows": len(rows),
            "page": page,
            "page_size": page_size,
            "total_pages": max((len(rows) + page_size - 1) // page_size, 1),
            "status": job["status"],
            "error": job.get("error", ""),
        }

    def update_row(
        self,
        job_id: str,
        row_id: int,
        *,
        weight_kg: Optional[float] = None,
        carrier: Optional[str] = None,
    ) -> dict[str, Any]:
        with self._lock:
            job = self.get(job_id)
            self._ensure_completed(job)
            row = job["rows"][row_id]
            updated = self.processor.update_row(row, weight_kg=weight_kg, carrier=carrier)
            job["rows"][row_id] = updated
            self._refresh_summary(job)
            self._persist(job_id)
            return self._public_row(updated)

    def bulk_apply_carrier(self, job_id: str, mtp_sku: str, carrier: str) -> dict[str, Any]:
        with self._lock:
            job = self.get(job_id)
            self._ensure_completed(job)
            updated_count = 0
            for index, row in enumerate(job["rows"]):
                if row.get("resolved_mtp_sku") != mtp_sku:
                    continue
                job["rows"][index] = self.processor.update_row(row, carrier=carrier)
                updated_count += 1
            self._refresh_summary(job)
            self._persist(job_id)
            return {"updated_rows": updated_count}

    def export(self, job_id: str, export_format: str) -> tuple[bytes, str]:
        job = self.get(job_id)
        self._ensure_completed(job)
        return self.processor.export_rows(job["rows"], export_format)

    @staticmethod
    def _public_row(row: dict[str, Any]) -> dict[str, Any]:
        public = dict(row)
        public.pop("raw_fields", None)
        return public

    def _refresh_summary(self, job: dict[str, Any]) -> None:
        rows = job["rows"]
        job["summary"]["exception_rows"] = sum(1 for row in rows if row["exception_reason"])
        job["summary"]["successful_rows"] = sum(1 for row in rows if not row["exception_reason"])
        job["summary"]["total_rows"] = len(rows)

    @staticmethod
    def _ensure_completed(job: dict[str, Any]) -> None:
        if job["status"] != "completed":
            raise ValueError("Job is still processing.")

    def _persist(self, job_id: str) -> None:
        path = JOB_DIR / f"{job_id}.json"
        path.write_text(json.dumps(self._jobs[job_id], indent=2), encoding="utf-8")

    def _process_job(self, job_id: str, uploads: list[dict[str, Any]]) -> None:
        try:
            payload = self.processor.process_uploads(uploads)
        except Exception as exc:  # pragma: no cover - background worker failure path
            with self._lock:
                job = self.get(job_id)
                job["status"] = "failed"
                job["error"] = str(exc)
                self._persist(job_id)
            return

        with self._lock:
            job = self.get(job_id)
            job["status"] = "completed"
            job["error"] = ""
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            job["summary"] = payload["summary"]
            job["rows"] = payload["rows"]
            self._persist(job_id)
