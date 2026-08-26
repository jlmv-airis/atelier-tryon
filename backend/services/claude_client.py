from anthropic import Anthropic

import config

SYSTEM_PROMPT = (
    "Actúa como fotógrafo profesional de moda. Mejora el realismo de esta escena:\n"
    "- iluminación tipo estudio\n"
    "- colores fieles a la prenda\n"
    "- textura realista de tela\n"
    "- eliminar artefactos\n"
    "- estilo editorial Vogue/Zara\n\n"
    "Devuelve un prompt optimizado para regenerar la imagen.\n\n"
    "Reglas de salida: responde UNICAMENTE con el prompt final en ingles, en un solo "
    "parrafo de maximo 120 palabras, sin titulos, sin comillas, sin explicaciones. "
    "Conserva exactamente la prenda, su color, corte y estampado, y la pose de la modelo."
)


def _build_content(image_description: str, image_url: str | None) -> list[dict]:
    content: list[dict] = []
    if image_url:
        content.append({"type": "image", "source": {"type": "url", "url": image_url}})
    content.append({"type": "text", "text": f"Descripción de la escena: {image_description}"})
    return content


def _extract_text(message) -> str:
    parts = [block.text for block in message.content if getattr(block, "type", "") == "text"]
    text = " ".join(parts).strip()
    if not text:
        raise RuntimeError("Claude no devolvio texto")
    return text.strip('"').strip()


def call_claude(image_description: str, image_url: str | None = None) -> str:
    """Devuelve un prompt optimizado a partir de la descripcion (y opcionalmente la imagen)."""
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=config.CLAUDE_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_content(image_description, image_url)}],
    )
    return _extract_text(message)
