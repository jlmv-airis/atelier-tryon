"""Proveedores gratuitos de Hugging Face: Space IDM-VTON (try-on), Inference API (refinado, text2img, LLM)."""
import io
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from gradio_client import Client, handle_file
from huggingface_hub import InferenceClient
from PIL import Image

import config


@lru_cache(maxsize=1)
def _inference() -> InferenceClient:
    return InferenceClient(token=config.HF_TOKEN, timeout=config.HF_TIMEOUT)


def _tmp_file(data: bytes, suffix: str) -> str:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    handle.write(data)
    handle.close()
    return handle.name


def _pil_to_jpeg(image: Image.Image, quality: int = 95) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def _path_to_jpeg(path: str) -> bytes:
    with Image.open(path) as image:
        return _pil_to_jpeg(image)


def _first_path(result) -> str:
    item = result[0] if isinstance(result, (list, tuple)) else result
    if isinstance(item, dict):
        item = item.get("path") or item.get("url")
    if not item or not Path(str(item)).exists():
        raise RuntimeError(f"El Space no devolvio un archivo de imagen: {item!r}")
    return str(item)


def tryon(garment: bytes, person: bytes, description: str) -> bytes:
    """Try-on via Space publico de IDM-VTON (ZeroGPU). Devuelve JPEG."""
    person_path = _tmp_file(person, ".jpg")
    garment_path = _tmp_file(garment, ".jpg")
    try:
        client = Client(config.HF_TRYON_SPACE, hf_token=config.HF_TOKEN or None, verbose=False)
        editor_value = {"background": handle_file(person_path), "layers": [], "composite": None}
        result = client.predict(
            editor_value,
            handle_file(garment_path),
            description or config.DEFAULT_GARMENT_DESCRIPTION,
            True,                     # is_checked: auto-mask
            False,                    # is_checked_crop
            config.TRYON_DENOISE_STEPS,
            42,                       # seed
            api_name=config.HF_TRYON_API_NAME,
        )
        return _path_to_jpeg(_first_path(result))
    finally:
        os.unlink(person_path)
        os.unlink(garment_path)


def refine(image: bytes, prompt: str) -> bytes:
    """Refinado img2img con la Inference API. Devuelve JPEG."""
    output = _inference().image_to_image(
        image,
        prompt=prompt,
        model=config.HF_REFINE_MODEL,
        strength=config.DIFFUSION_PROMPT_STRENGTH,
        num_inference_steps=config.DIFFUSION_STEPS,
        guidance_scale=max(config.DIFFUSION_GUIDANCE, 5.0),
    )
    return _pil_to_jpeg(output)


def text_to_image(prompt: str, width: int = 768, height: int = 1024, seed: int | None = None) -> bytes:
    """Genera una imagen desde texto (FLUX.1-schnell). Devuelve JPEG."""
    output = _inference().text_to_image(
        prompt, model=config.HF_TEXT2IMG_MODEL, width=width, height=height, seed=seed
    )
    return _pil_to_jpeg(output)


def _chat(model: str, content: list[dict], system: str) -> str:
    response = _inference().chat_completion(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
        max_tokens=config.CLAUDE_MAX_TOKENS,
        temperature=0.4,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("LLM devolvio texto vacio")
    return text.strip('"').strip()


def improve_prompt(system: str, description: str, image_url: str | None) -> str:
    """LLM abierto con vision; si falla, modelo solo texto."""
    text = {"type": "text", "text": f"Descripción de la escena: {description}"}
    if image_url:
        try:
            image = {"type": "image_url", "image_url": {"url": image_url}}
            return _chat(config.HF_LLM_MODEL, [image, text], system)
        except Exception:
            pass
    return _chat(config.HF_LLM_TEXT_MODEL, [text], system)
