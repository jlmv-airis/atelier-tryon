from dataclasses import asdict, dataclass
from typing import Callable

import config
from services import ai
from services.category import detect as detect_category
from services.storage import download, upload_bytes

ProgressFn = Callable[[str], None]


@dataclass
class TryOnResult:
    base_image_url: str
    improved_prompt: str
    final_image_url: str
    refined: bool
    category: str

    def to_dict(self) -> dict:
        return asdict(self)


def build_scene_description(garment_description: str) -> str:
    garment = garment_description or "a women's fashion garment"
    return (
        f"Virtual try-on result: a female model wearing {garment}. "
        "The image comes from an AI try-on model and may contain artifacts, "
        "flat lighting or unrealistic fabric texture."
    )


def resolve_person(person_image: bytes | None) -> bytes:
    if person_image is not None:
        return person_image
    if not config.DEFAULT_PERSON_IMAGE_URL:
        raise ValueError("Falta foto de persona: envia 'person' o configura DEFAULT_PERSON_IMAGE_URL")
    return download(config.DEFAULT_PERSON_IMAGE_URL)[0]


def _store(job_id: str, name: str, data: bytes) -> str:
    url = upload_bytes(f"jobs/{job_id}/{name}", data)
    if not url:
        raise RuntimeError("Storage no configurado")
    return url


def resolve_category(requested: str | None, garment_image: bytes, garment_description: str) -> str:
    wanted = requested if requested and requested != "auto" else config.TRYON_CATEGORY
    return detect_category(wanted, garment_description, classify=lambda: ai.classify_garment(garment_image))


def run_pipeline(
    job_id: str,
    garment_image: bytes,
    person_image: bytes | None,
    garment_description: str,
    on_progress: ProgressFn = lambda stage: None,
    category: str | None = None,
) -> TryOnResult:
    on_progress("tryon")
    category = resolve_category(category, garment_image, garment_description)
    base = ai.tryon(garment_image, resolve_person(person_image), garment_description, category)
    base_url = _store(job_id, "base.jpg", base)

    on_progress("claude")
    prompt = ai.improve_prompt(build_scene_description(garment_description), base_url)

    on_progress("refine")
    refined = ai.refine(base, base_url, prompt)
    final_url = _store(job_id, "final.jpg", refined) if refined else base_url

    return TryOnResult(base_url, prompt, final_url, refined is not None, category)
