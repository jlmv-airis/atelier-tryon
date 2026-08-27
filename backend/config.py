import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _bool(name: str, default: bool) -> bool:
    return _env(name, "1" if default else "0").lower() in ("1", "true", "yes")


# --- Proveedor de IA: "hf" (gratis, Hugging Face) o "replicate" (pago) ---
AI_PROVIDER = _env("AI_PROVIDER", "hf").lower()

# Hugging Face (gratis con cuenta y token de lectura)
HF_TOKEN = _env("HF_TOKEN")
HF_TRYON_SPACE = _env("HF_TRYON_SPACE", "yisol/IDM-VTON")
HF_TRYON_API_NAME = _env("HF_TRYON_API_NAME", "/tryon")
HF_REFINE_MODEL = _env("HF_REFINE_MODEL", "black-forest-labs/FLUX.2-klein-4B")
HF_TEXT2IMG_MODEL = _env("HF_TEXT2IMG_MODEL", "black-forest-labs/FLUX.1-schnell")
HF_LLM_MODEL = _env("HF_LLM_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
HF_LLM_TEXT_MODEL = _env("HF_LLM_TEXT_MODEL", "Qwen/Qwen3.5-9B")
HF_TIMEOUT = int(_env("HF_TIMEOUT", "600"))

# Replicate (opcional, pago)
REPLICATE_API_TOKEN = _env("REPLICATE_API_TOKEN")
TRYON_MODEL = _env(
    "TRYON_MODEL",
    "cuuupid/idm-vton:0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985",
)
DIFFUSION_MODEL = _env("DIFFUSION_MODEL", "black-forest-labs/flux-dev")

# Parametros comunes de generacion
DIFFUSION_PROMPT_STRENGTH = float(_env("DIFFUSION_PROMPT_STRENGTH", "0.35"))
DIFFUSION_STEPS = int(_env("DIFFUSION_STEPS", "28"))
DIFFUSION_GUIDANCE = float(_env("DIFFUSION_GUIDANCE", "3.0"))
TRYON_DENOISE_STEPS = int(_env("TRYON_DENOISE_STEPS", "30"))
TRYON_CATEGORY = _env("TRYON_CATEGORY", "upper_body")
REFINE_REQUIRED = _bool("REFINE_REQUIRED", False)   # False: si el refinado falla, se entrega la base

# Mejora de prompt: Claude si hay key (pago), si no LLM de Hugging Face (gratis)
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
CLAUDE_MODEL = _env("CLAUDE_MODEL", "claude-sonnet-4-5")
CLAUDE_MAX_TOKENS = int(_env("CLAUDE_MAX_TOKENS", "600"))

DEFAULT_PERSON_IMAGE_URL = _env("DEFAULT_PERSON_IMAGE_URL")
DEFAULT_GARMENT_DESCRIPTION = _env("DEFAULT_GARMENT_DESCRIPTION", "women's fashion garment")

# --- Supabase: base de datos + storage (gratis) ---
SUPABASE_URL = _env("SUPABASE_URL")
SUPABASE_SERVICE_KEY = _env("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = _env("SUPABASE_BUCKET", "tryon")

# --- Storage S3-compatible alternativo (R2/S3), opcional ---
S3_ENDPOINT_URL = _env("S3_ENDPOINT_URL")
S3_ACCESS_KEY_ID = _env("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = _env("S3_SECRET_ACCESS_KEY")
S3_BUCKET = _env("S3_BUCKET", "tryon")
S3_REGION = _env("S3_REGION", "auto")
S3_PUBLIC_BASE_URL = _env("S3_PUBLIC_BASE_URL")

# --- App ---
CORS_ORIGINS = [o.strip() for o in _env("CORS_ORIGINS", "*").split(",") if o.strip()]
PORT = int(_env("PORT", "8000"))
JOB_TTL_SECONDS = int(_env("JOB_TTL_SECONDS", "86400"))


def db_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


def s3_enabled() -> bool:
    return bool(S3_ENDPOINT_URL and S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY and S3_PUBLIC_BASE_URL)


def storage_enabled() -> bool:
    return db_enabled() or s3_enabled()


def prompt_provider() -> str:
    return "claude" if ANTHROPIC_API_KEY else "hf"


def validate_config() -> list[str]:
    missing = []
    if AI_PROVIDER == "replicate" and not REPLICATE_API_TOKEN:
        missing.append("REPLICATE_API_TOKEN")
    if AI_PROVIDER == "hf" and not HF_TOKEN:
        missing.append("HF_TOKEN")
    if not storage_enabled():
        missing.append("SUPABASE_URL+SUPABASE_SERVICE_KEY (storage)")
    return missing
