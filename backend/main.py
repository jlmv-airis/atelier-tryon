import asyncio
import json
import logging

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import config
import jobs
from services.images import normalize_image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tryon")

app = FastAPI(title="Virtual Try-On Cloud API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_BYTES = 12 * 1024 * 1024
TERMINAL = {"done", "error"}


async def _read_image(upload: UploadFile | None, field: str) -> bytes | None:
    if upload is None:
        return None
    data = await upload.read()
    if not data:
        raise HTTPException(400, f"{field}: archivo vacio")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"{field}: excede {MAX_BYTES // (1024 * 1024)} MB")
    try:
        return normalize_image(data)
    except ValueError as exc:
        raise HTTPException(400, f"{field}: {exc}") from exc


@app.get("/health")
def health():
    return {
        "status": "ok",
        "missing_env": config.validate_config(),
        "storage": config.storage_enabled(),
        "database": config.db_enabled(),
        "ai_provider": config.AI_PROVIDER,
        "prompt_provider": config.prompt_provider(),
    }


@app.post("/tryon", status_code=202)
async def create_tryon(
    background: BackgroundTasks,
    image: UploadFile = File(...),
    person: UploadFile | None = File(None),
    description: str = Form(""),
    user_id: str = Form("anonymous"),
    category: str = Form("auto"),
):
    missing = config.validate_config()
    if missing:
        raise HTTPException(500, f"Faltan variables de entorno: {', '.join(missing)}")
    garment = await _read_image(image, "image")
    person_bytes = await _read_image(person, "person")
    if person_bytes is None and not config.DEFAULT_PERSON_IMAGE_URL:
        raise HTTPException(400, "Envia 'person' o configura DEFAULT_PERSON_IMAGE_URL")
    if not config.storage_enabled():
        raise HTTPException(500, "Storage no configurado (SUPABASE_URL + SUPABASE_SERVICE_KEY)")

    job = jobs.create_job(user_id, garment, person_bytes, description, category)
    background.add_task(jobs.process_job, job["id"], garment, person_bytes, description, category)
    return jobs.public_view(job)


@app.get("/tryon/{job_id}")
def get_tryon(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job no encontrado")
    return job


@app.get("/tryon/{job_id}/events")
async def stream_tryon(job_id: str):
    if jobs.get_job(job_id) is None:
        raise HTTPException(404, "Job no encontrado")

    async def generator():
        last = None
        while True:
            job = jobs.get_job(job_id)
            if job != last:
                yield f"data: {json.dumps(job)}\n\n"
                last = job
            if job is None or job["status"] in TERMINAL:
                break
            await asyncio.sleep(2)

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/results")
def list_results(user_id: str = Query("anonymous"), limit: int = Query(20, le=100)):
    return {"items": jobs.list_jobs(user_id, limit)}
