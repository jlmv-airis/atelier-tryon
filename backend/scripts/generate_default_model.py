"""Genera la modelo por defecto (mujer, cuerpo completo, 3:4, fondo liso) y la sube al storage.

Uso (desde backend/):  python -m scripts.generate_default_model [--out default.jpg] [--seed 7] [--no-upload]
Requiere: HF_TOKEN (o REPLICATE_API_TOKEN con AI_PROVIDER=replicate) y SUPABASE_URL + SUPABASE_SERVICE_KEY.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from services import ai  # noqa: E402
from services.storage import ensure_supabase_bucket, upload_bytes  # noqa: E402

MODEL_KEY = "models/default.jpg"

PROMPT = (
    "Full-body studio photograph of a young adult female fashion model standing upright, "
    "facing the camera directly, arms relaxed at her sides, neutral calm expression, "
    "wearing a plain fitted white crew-neck t-shirt tucked into slim dark blue jeans and simple white sneakers, "
    "hair tied back, no accessories. Entire body visible from top of head to feet with clear margin above and below, "
    "centered in frame, vertical 3:4 portrait. Seamless plain light gray studio backdrop, soft even diffused lighting, "
    "no shadows on the background, sharp focus, photorealistic, e-commerce lookbook photography, high detail skin and fabric."
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="default.jpg")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--no-upload", action="store_true")
    args = parser.parse_args()

    data = ai.generate_default_person(PROMPT, seed=args.seed)
    Path(args.out).write_bytes(data)
    print(f"local: {args.out} ({len(data) // 1024} KB)")

    if args.no_upload:
        return 0
    if not config.storage_enabled():
        print("Storage no configurado; imagen solo guardada en local", file=sys.stderr)
        return 2
    if config.db_enabled() and not config.s3_enabled():
        ensure_supabase_bucket()
    public_url = upload_bytes(MODEL_KEY, data, "image/jpeg")
    print(f"DEFAULT_PERSON_IMAGE_URL={public_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
