"""Fachada de IA: elige proveedor (hf gratis / replicate pago) y unifica la salida en bytes JPEG."""
import logging

import config
from services import hf_client
from services.claude_client import SYSTEM_PROMPT, call_claude
from services.storage import download

logger = logging.getLogger("tryon.ai")

FALLBACK_PROMPT = (
    "Editorial fashion photograph of the same model wearing the same garment, identical pose and framing, "
    "professional studio lighting with soft key light and subtle rim light, true-to-life garment colors, "
    "realistic fabric texture and natural drape, clean skin, no artifacts, sharp focus, "
    "Vogue and Zara lookbook style, high-end retouching."
)


def tryon(garment: bytes, person: bytes, description: str, category: str = "upper_body") -> bytes:
    if config.AI_PROVIDER == "replicate":
        from services.replicate_client import call_tryon_model

        url = call_tryon_model(garment, person, description, category)
        return download(url)[0]
    return hf_client.tryon(garment, person, description, category)


def classify_garment(garment: bytes) -> str | None:
    try:
        return hf_client.classify_garment(garment)
    except Exception as exc:
        logger.warning("clasificacion de prenda fallo (%s)", hf_client.describe_error(exc))
        return None


CONSISTENCY_SUFFIX = (
    " Keep the exact same model, identical full-body framing from head to shoes, the same standing pose, "
    "the same garment shape, color and print, and the same plain background. Do not crop, zoom or change the composition."
)


def _with_consistency(prompt: str) -> str:
    return prompt.rstrip() + CONSISTENCY_SUFFIX


def improve_prompt(description: str, base_image_url: str) -> str:
    try:
        if config.prompt_provider() == "claude":
            return _with_consistency(call_claude(description, image_url=base_image_url))
        return _with_consistency(hf_client.improve_prompt(SYSTEM_PROMPT, description, base_image_url))
    except Exception as exc:
        logger.warning("mejora de prompt fallo (%s); usando prompt fijo", hf_client.describe_error(exc))
        return _with_consistency(FALLBACK_PROMPT)


def refine(base_image: bytes, base_image_url: str, prompt: str) -> bytes | None:
    """Devuelve la imagen refinada, o None si falla y el refinado no es obligatorio."""
    try:
        if config.AI_PROVIDER == "replicate":
            from services.replicate_client import call_diffusion

            return download(call_diffusion(prompt, init_image_url=base_image_url))[0]
        return hf_client.refine(base_image, prompt)
    except Exception as exc:
        if config.REFINE_REQUIRED:
            raise
        logger.warning("refinado fallo (%s); se entrega la imagen base", hf_client.describe_error(exc))
        return None


def generate_default_person(prompt: str, seed: int | None = None) -> bytes:
    if config.AI_PROVIDER == "replicate":
        from services.replicate_client import call_diffusion

        return download(call_diffusion(prompt, init_image_url=None, seed=seed))[0]
    return hf_client.text_to_image(prompt, seed=seed)
