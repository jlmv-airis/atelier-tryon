"""Normalizacion de imagenes de entrada: cualquier formato (HEIC incluido) -> JPEG RGB, orientacion corregida."""
import io

from PIL import Image, ImageOps

try:  # HEIC/HEIF de iPhone
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:  # pragma: no cover - dependencia opcional
    pass

MAX_SIDE = 1024
JPEG_QUALITY = 92


def normalize_image(data: bytes, max_side: int = MAX_SIDE) -> bytes:
    """Devuelve JPEG RGB con EXIF aplicado y lado mayor <= max_side. Lanza ValueError si no es imagen."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
            image.thumbnail((max_side, max_side), Image.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            return buffer.getvalue()
    except Exception as exc:
        raise ValueError(f"imagen no valida: {exc}") from exc
