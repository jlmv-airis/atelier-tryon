import os
import time

os.environ["AI_PROVIDER"] = "hf"
os.environ["HF_TOKEN"] = "test"
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "test"
os.environ["DEFAULT_PERSON_IMAGE_URL"] = "https://example.com/model.jpg"

from fastapi.testclient import TestClient  # noqa: E402

import jobs  # noqa: E402
import main  # noqa: E402
import pipeline  # noqa: E402
import services.ai as ai  # noqa: E402
import services.db as db  # noqa: E402

import io
from PIL import Image as _PILImage
_buf = io.BytesIO(); _PILImage.new("RGB", (64, 96), (200, 30, 40)).save(_buf, format="JPEG"); IMG = _buf.getvalue()
CALLS: list[str] = []


def _fake_tryon(garment, person, description):
    CALLS.append("tryon")
    assert garment[:3] == b"\xff\xd8\xff" and person == b"person-bytes"
    return b"base-bytes"


def _fake_prompt(description, base_url):
    CALLS.append("prompt")
    assert base_url.endswith("/jobs/") or "/jobs/" in base_url
    return "editorial studio prompt"


def _fake_refine(base, base_url, prompt):
    CALLS.append("refine")
    assert base == b"base-bytes" and prompt == "editorial studio prompt"
    return b"final-bytes"


def _fake_upload(key, data, content_type="image/jpeg"):
    return f"https://test.supabase.co/storage/v1/object/public/tryon/{key}"


def _fake_download(url):
    return b"person-bytes", "image/jpeg"


def setup_module(module):
    ai.tryon = _fake_tryon
    ai.improve_prompt = _fake_prompt
    ai.refine = _fake_refine
    pipeline.upload_bytes = _fake_upload
    pipeline.download = _fake_download
    jobs.upload_bytes = _fake_upload
    memory = db.MemoryStore()
    jobs.get_store = lambda: memory  # memoria en tests (no Supabase real)


def _wait_done(client, job_id, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/tryon/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("job no termino")


def test_health():
    with TestClient(main.app) as client:
        body = client.get("/health").json()
        assert body["status"] == "ok" and body["missing_env"] == []
        assert body["ai_provider"] == "hf" and body["prompt_provider"] == "hf"


def test_tryon_full_flow():
    CALLS.clear()
    with TestClient(main.app) as client:
        r = client.post(
            "/tryon",
            files={"image": ("g.jpg", IMG, "image/jpeg")},
            data={"description": "vestido rojo", "user_id": "u1"},
        )
        assert r.status_code == 202, r.text
        job = _wait_done(client, r.json()["id"])
        assert job["status"] == "done", job
        assert CALLS == ["tryon", "prompt", "refine"]
        assert job["base_image_url"].endswith("/base.jpg")
        assert job["final_image_url"].endswith("/final.jpg")
        assert job["improved_prompt"] == "editorial studio prompt"
        assert job["refined"] is True
        items = client.get("/results", params={"user_id": "u1"}).json()["items"]
        assert items[0]["id"] == job["id"]


def test_refine_failure_falls_back_to_base():
    original = ai.refine
    ai.refine = lambda base, base_url, prompt: None
    try:
        with TestClient(main.app) as client:
            r = client.post("/tryon", files={"image": ("g.jpg", IMG, "image/jpeg")})
            job = _wait_done(client, r.json()["id"])
            assert job["status"] == "done"
            assert job["final_image_url"] == job["base_image_url"]
            assert job["refined"] is False
    finally:
        ai.refine = original


def test_tryon_rejects_bad_type():
    with TestClient(main.app) as client:
        r = client.post("/tryon", files={"image": ("g.txt", b"abc", "text/plain")})
        assert r.status_code == 400


def test_job_not_found():
    with TestClient(main.app) as client:
        assert client.get("/tryon/nope").status_code == 404
