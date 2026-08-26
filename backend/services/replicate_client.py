import io
from typing import Any

import replicate

import config

ImageInput = str | bytes


def _to_replicate_input(image: ImageInput, filename: str) -> Any:
    """Acepta URL (str) o bytes. Los bytes se suben como archivo."""
    if isinstance(image, str):
        return image
    buffer = io.BytesIO(image)
    buffer.name = filename
    return buffer


def _first_url(output: Any) -> str:
    """Normaliza la salida de replicate.run (FileOutput, lista o str) a una URL."""
    if isinstance(output, (list, tuple)):
        if not output:
            raise RuntimeError("Replicate devolvio una lista vacia")
        output = output[0]
    if isinstance(output, str):
        return output
    url = getattr(output, "url", None)
    if url:
        return url
    raise RuntimeError(f"Salida de Replicate no reconocida: {type(output)}")


def call_tryon_model(
    garment_image: ImageInput,
    person_image: ImageInput | None = None,
    garment_description: str = "",
) -> str:
    """Genera la imagen base de try-on. Devuelve URL."""
    person = person_image if person_image is not None else config.DEFAULT_PERSON_IMAGE_URL
    if not person:
        raise ValueError("Falta foto de persona: envia 'person' o configura DEFAULT_PERSON_IMAGE_URL")
    payload = {
        "human_img": _to_replicate_input(person, "person.jpg"),
        "garm_img": _to_replicate_input(garment_image, "garment.jpg"),
        "garment_des": garment_description or config.DEFAULT_GARMENT_DESCRIPTION,
        "category": config.TRYON_CATEGORY,
        "is_checked": True,
        "is_checked_crop": True,
        "denoise_steps": config.TRYON_DENOISE_STEPS,
        "seed": 42,
    }
    output = replicate.run(config.TRYON_MODEL, input=payload)
    return _first_url(output)


def call_diffusion(prompt: str, init_image_url: str | None = None, seed: int | None = None) -> str:
    """Regenera/refina con el prompt optimizado. Devuelve URL."""
    payload = {
        "prompt": prompt,
        "num_inference_steps": config.DIFFUSION_STEPS,
        "guidance": config.DIFFUSION_GUIDANCE,
        "num_outputs": 1,
        "output_format": "jpg",
        "output_quality": 95,
    }
    if seed is not None:
        payload["seed"] = seed
    if init_image_url:
        payload["image"] = init_image_url
        payload["prompt_strength"] = config.DIFFUSION_PROMPT_STRENGTH
    else:
        payload["aspect_ratio"] = "3:4"
    output = replicate.run(config.DIFFUSION_MODEL, input=payload)
    return _first_url(output)
