"""Proveedores gratuitos de Hugging Face: Space IDM-VTON (try-on), Inference API (refinado, text2img, LLM)."""
import io
import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from gradio_client import Client, handle_file
from huggingface_hub import InferenceClient
from PIL import Image

import config

logger = logging.getLogger("tryon.hf")


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


def _iter_candidates(node):
    """Recorre recursivamente la salida del Space y produce posibles rutas/URLs de imagen."""
    if node is None:
        return
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key in ("image", "path", "url", "value", "file"):
            if key in node:
                yield from _iter_candidates(node[key])
        for key, value in node.items():
            if key not in ("image", "path", "url", "value", "file"):
                yield from _iter_candidates(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _iter_candidates(item)


def _first_path(result) -> str:
    for candidate in _iter_candidates(result):
        if Path(candidate).exists():
            return candidate
    raise RuntimeError(f"El Space no devolvio un archivo de imagen: {repr(result)[:300]}")


def _space_client(space: str) -> Client:
    """gradio_client >= 1.x usa `token`; versiones antiguas usaban `hf_token`."""
    token = config.HF_TOKEN or None
    try:
        return Client(space, token=token, verbose=False)
    except TypeError:
        return Client(space, hf_token=token, verbose=False)


DC_CATEGORY = {"upper_body": "Upper-body", "lower_body": "Lower-body", "dresses": "Dress"}


def tryon(garment: bytes, person: bytes, description: str, category: str = "upper_body") -> bytes:
    """Try-on: IDM-VTON para parte superior; OOTDiffusion (cuerpo completo) para vestidos y parte de abajo."""
    person_path = _tmp_file(person, ".jpg")
    garment_path = _tmp_file(garment, ".jpg")
    client = None
    try:
        if category == "upper_body":
            client = _space_client(config.HF_TRYON_SPACE)
            result = _predict_idm(client, person_path, garment_path, description)
        else:
            client = _space_client(config.HF_TRYON_DC_SPACE)
            result = _predict_ootd(client, person_path, garment_path, category)
        return _path_to_jpeg(_first_path(result))
    finally:
        _close_quietly(client)   # detiene el hilo de heartbeat de gradio_client
        os.unlink(person_path)
        os.unlink(garment_path)


def _predict_idm(client: Client, person_path: str, garment_path: str, description: str):
    editor_value = {"background": handle_file(person_path), "layers": [], "composite": None}
    return client.predict(
        editor_value,
        handle_file(garment_path),
        description or config.DEFAULT_GARMENT_DESCRIPTION,
        True,                     # is_checked: auto-mask
        False,                    # is_checked_crop
        config.TRYON_DENOISE_STEPS,
        42,                       # seed
        api_name=config.HF_TRYON_API_NAME,
    )


def _predict_ootd(client: Client, person_path: str, garment_path: str, category: str):
    return client.predict(
        vton_img=handle_file(person_path),
        garm_img=handle_file(garment_path),
        category=DC_CATEGORY.get(category, "Upper-body"),
        n_samples=1,
        n_steps=config.HF_TRYON_DC_STEPS,
        image_scale=config.HF_TRYON_DC_SCALE,
        seed=42,
        api_name=config.HF_TRYON_DC_API_NAME,
    )


def classify_garment(image: bytes) -> str | None:
    """Clasifica la prenda con el LLM de vision: upper_body | lower_body | dresses."""
    import base64

    data_url = "data:image/jpeg;base64," + base64.b64encode(image).decode()
    content = [
        {"type": "image_url", "image_url": {"url": data_url}},
        {"type": "text", "text": "Classify this garment. Answer with exactly one word: upper_body, lower_body or dresses."},
    ]
    answer = _chat(config.HF_LLM_MODEL, content, "You are a fashion catalog classifier. Reply with one word only.")
    return answer.strip().lower().split()[0].strip(".,")


def _close_quietly(client) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


def describe_error(exc: Exception) -> str:
    """Texto util para logs: tipo, mensaje y, si es HTTP, status y cuerpo."""
    parts = [type(exc).__name__, " ".join(str(exc).split())[:400]]
    response = getattr(exc, "response", None)
    if response is not None:
        parts.append(f"status={getattr(response, 'status_code', '?')}")
        parts.append("body=" + " ".join(str(getattr(response, 'text', '')).split())[:300])
    return " | ".join(p for p in parts if p)


def refine(image: bytes, prompt: str) -> bytes:
    """Refinado img2img (modelos de edicion tipo FLUX Kontext/klein). Devuelve JPEG."""
    client = _inference()
    try:
        output = client.image_to_image(
            image,
            prompt=prompt,
            model=config.HF_REFINE_MODEL,
            guidance_scale=config.DIFFUSION_GUIDANCE,
            num_inference_steps=config.DIFFUSION_STEPS,
        )
    except (TypeError, ValueError, KeyError):
        # Algunos proveedores rechazan parametros extra: reintento solo con el prompt
        output = client.image_to_image(image, prompt=prompt, model=config.HF_REFINE_MODEL)
    return _pil_to_jpeg(output)


def text_to_image(prompt: str, width: int = 768, height: int = 1024, seed: int | None = None) -> bytes:
    """Genera una imagen desde texto (FLUX.1-schnell). Devuelve JPEG."""
    output = _inference().text_to_image(
        prompt, model=config.HF_TEXT2IMG_MODEL, width=width, height=height, seed=seed
    )
    return _pil_to_jpeg(output)


def _message_text(response) -> str:
    message = response.choices[0].message
    text = (getattr(message, "content", None) or "").strip()
    if not text:  # modelos "thinking": el texto util puede venir en reasoning_content
        text = (getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None) or "").strip()
    return text


def _chat(model: str, content: list[dict], system: str) -> str:
    client = _inference()
    messages = [{"role": "system", "content": system + " /no_think"}, {"role": "user", "content": content}]
    kwargs = dict(model=model, messages=messages, max_tokens=max(config.CLAUDE_MAX_TOKENS, 1200), temperature=0.4)
    try:
        response = client.chat_completion(
            **kwargs, extra_body={"chat_template_kwargs": {"enable_thinking": False}}
        )
    except Exception:
        response = client.chat_completion(**kwargs)
    text = _message_text(response)
    if not text:
        raise RuntimeError(f"LLM {model} devolvio texto vacio")
    return text.strip('"').strip()


def improve_prompt(system: str, description: str, image_url: str | None) -> str:
    """LLM abierto con vision; si falla, modelo solo texto."""
    text = {"type": "text", "text": f"Descripción de la escena: {description}"}
    if image_url:
        try:
            image = {"type": "image_url", "image_url": {"url": image_url}}
            return _chat(config.HF_LLM_MODEL, [image, text], system)
        except Exception as exc:
            logger.warning("LLM con vision fallo (%s); probando solo texto", describe_error(exc))
    return _chat(config.HF_LLM_TEXT_MODEL, [text], system)
