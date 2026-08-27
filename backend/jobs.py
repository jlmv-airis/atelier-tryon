"""Logica de jobs: creacion, ejecucion en background y consulta. No toca Sheets/DB directamente."""
import logging
import time
import uuid
from datetime import datetime, timezone

import config
from pipeline import run_pipeline
from services.db import get_store
from services.storage import upload_bytes

logger = logging.getLogger("tryon.jobs")

STAGES = ["queued", "tryon", "claude", "refine", "done", "error"]
PUBLIC_FIELDS = (
    "id", "user_id", "status", "stage", "description", "garment_url", "person_url",
    "base_image_url", "improved_prompt", "final_image_url", "refined", "category", "error", "created_at", "updated_at",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_view(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {k: row.get(k) for k in PUBLIC_FIELDS}


def create_job(user_id: str, garment: bytes, person: bytes | None, description: str, category: str = "auto") -> dict:
    job_id = uuid.uuid4().hex
    garment_url = upload_bytes(f"jobs/{job_id}/garment.jpg", garment)
    person_url = upload_bytes(f"jobs/{job_id}/person.jpg", person) if person else None
    row = {
        "id": job_id,
        "user_id": user_id,
        "status": "queued",
        "stage": "queued",
        "description": description,
        "category": category,
        "garment_url": garment_url,
        "person_url": person_url,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "created_ts": time.time(),
    }
    return get_store().insert(row)


def _set_stage(job_id: str, stage: str) -> None:
    get_store().update(job_id, {"status": "processing", "stage": stage, "updated_at": _now_iso()})


def process_job(job_id: str, garment: bytes, person: bytes | None, description: str, category: str = "auto") -> None:
    try:
        result = run_pipeline(job_id, garment, person, description, on_progress=lambda s: _set_stage(job_id, s), category=category)
        get_store().update(job_id, {"status": "done", "stage": "done", "updated_at": _now_iso(), **result.to_dict()})
        logger.info("job %s done -> %s", job_id, result.final_image_url)
    except Exception as exc:
        logger.exception("job %s failed", job_id)
        get_store().update(job_id, {"status": "error", "stage": "error", "error": str(exc), "updated_at": _now_iso()})
    finally:
        get_store().purge_older_than(config.JOB_TTL_SECONDS)


def get_job(job_id: str) -> dict | None:
    return public_view(get_store().get(job_id))


def list_jobs(user_id: str, limit: int = 20) -> list[dict]:
    return [public_view(r) for r in get_store().list_by_user(user_id, limit)]
