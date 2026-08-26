"""Crea el bucket publico de Supabase Storage (idempotente). Uso: python -m scripts.bootstrap_storage"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from services.storage import ensure_supabase_bucket, upload_bytes  # noqa: E402


def main() -> int:
    if not config.db_enabled():
        print("Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY", file=sys.stderr)
        return 1
    ensure_supabase_bucket()
    url = upload_bytes("health/ping.txt", b"ok", "text/plain")
    print(f"bucket '{config.SUPABASE_BUCKET}' listo; prueba publica: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
