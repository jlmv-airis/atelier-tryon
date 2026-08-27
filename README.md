# Atelier — Virtual Try-On (cloud, gratis)

Web app móvil + backend FastAPI + pipeline IA (IDM-VTON → LLM → refinado) con deploy automático. Stack gratuito: Vercel + Render Free + Supabase + Hugging Face + GitHub Actions.

- **Puesta en marcha y operación:** [FREE-STACK.md](FREE-STACK.md)
- Variante de pago (Railway + R2 + Replicate + Claude): `docs/paid-stack/`
- Frontend: `frontend/` · Backend: `backend/` · DB: `supabase/schema.sql`

## Workflows

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `bootstrap.yml` | manual, una vez | bucket + modelo por defecto + schema + variables Render + deploy backend |
| `backend.yml` | push a `backend/**` | pytest → docker build → deploy Render → smoke `/health` |
| `frontend.yml` | push a `frontend/**` | build check (Vercel despliega solo en cada push) |
| `e2e.yml` | manual / lunes | try-on real contra producción, artefacto con imágenes |
| `keepalive.yml` | cada 14 min (06–24 h CDMX) | ping `/health` para que Render Free no duerma |

## Desarrollo en cloud (Codespaces)

```bash
cd backend && pip install -r requirements.txt && cp .env.example .env && uvicorn main:app --port 8000
cd frontend && npm install && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
cd backend && python -m pytest -q tests
```
