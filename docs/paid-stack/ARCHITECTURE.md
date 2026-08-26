# Atelier — Virtual Try-On 100% cloud

Sin Mac, sin Xcode, sin entorno local. Todo se ejecuta en cloud y se despliega con `git push`.

---

## 1. Arquitectura (diagrama textual)

```
                         ┌────────────────────────────────────────────┐
                         │  USUARIO (Safari iOS / Chrome Android / web)│
                         └───────────────┬────────────────────────────┘
                                         │ HTTPS
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND · Next.js 14 (App Router) · Vercel Edge/CDN                        │
│  - Upload prenda (+ foto persona opcional)                                   │
│  - POST /tryon → recibe job_id (202)                                         │
│  - Suscripción SSE /tryon/{id}/events (fallback polling 2.5 s)               │
│  - Muestra base vs. refinada + prompt de Claude + historial (/results)       │
└───────────────┬─────────────────────────────────────────────────────────────┘
                │ HTTPS (CORS)                       ▲ imágenes públicas (CDN R2)
                ▼                                   │
┌─────────────────────────────────────────────────────────────────────────────┐
│  BACKEND · FastAPI · Docker · Railway (autoscale, /health)                    │
│                                                                              │
│   POST /tryon ──► jobs.create_job ──► R2: garment.jpg, person.jpg           │
│                   └─► BackgroundTask: jobs.process_job                       │
│                                                                              │
│   pipeline.run_pipeline                                                      │
│   ① call_tryon_model  ──► Replicate · IDM-VTON (GPU)   ─► R2 base.png       │
│   ② call_claude       ──► Anthropic · Claude (visión)  ─► improved_prompt   │
│   ③ call_diffusion    ──► Replicate · FLUX dev img2img  ─► R2 final.jpg     │
│                                                                              │
│   estado del job: queued → tryon → claude → refine → done | error           │
└──────┬──────────────────────┬──────────────────────────────┬────────────────┘
       │                      │                              │
       ▼                      ▼                              ▼
┌──────────────┐   ┌──────────────────────┐   ┌────────────────────────────┐
│ Cloudflare R2│   │ Supabase Postgres    │   │ GPU cloud (Replicate)      │
│ S3-compatible│   │ users · outfits ·    │   │ + Anthropic API            │
│ bucket público│  │ tryon_jobs           │   │                            │
└──────────────┘   └──────────────────────┘   └────────────────────────────┘

CI/CD:  git push main ─► GitHub Actions ─┬─► backend/**  → pytest → docker build → railway up → smoke /health
                                         └─► frontend/** → npm build → vercel deploy --prod
```

Por qué `/tryon` es asíncrono: el pipeline tarda 60–180 s. Vercel y los proxies de Railway/Render cortan peticiones largas; el job devuelve `202` al instante y el cliente recibe el progreso por SSE (o polling), lo que da la sensación de tiempo real sin mantener una petición abierta 3 minutos.

---

## 2. Estructura del repositorio (monorepo)

```
tryon-cloud/
├── .github/workflows/
│   ├── backend.yml            # test → docker build → Railway deploy → smoke test
│   └── frontend.yml           # build → Vercel preview (PR) / production (main)
├── backend/
│   ├── main.py                # FastAPI: /health, /tryon, /tryon/{id}, /tryon/{id}/events, /results
│   ├── jobs.py                # lógica de jobs (crear, procesar en background, consultar)
│   ├── pipeline.py            # try-on → Claude → refinado (puro, sin I/O de DB)
│   ├── config.py              # variables de entorno
│   ├── services/
│   │   ├── replicate_client.py    # call_tryon_model(), call_diffusion()
│   │   ├── claude_client.py       # call_claude()
│   │   ├── storage.py             # R2/S3: upload_bytes(), mirror_url()
│   │   └── db.py                  # Supabase o memoria: insert/update/get/list
│   ├── tests/test_api.py      # flujo completo con proveedores simulados (corre en CI)
│   ├── Dockerfile
│   ├── railway.json           # builder Docker + healthcheck
│   ├── fly.toml               # alternativa Fly.io (no cableada en CI)
│   ├── render.yaml            # alternativa Render (no cableada en CI)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx           # upload → job → resultado → historial
│   │   └── globals.css        # UI Apple premium (light/dark)
│   ├── components/
│   │   ├── UploadCard.tsx
│   │   └── ResultPanel.tsx
│   ├── lib/api.ts             # createTryOn, getTryOn, subscribeToJob (SSE + fallback), listResults
│   ├── next.config.mjs
│   ├── vercel.json
│   ├── package.json
│   └── .env.example
├── supabase/schema.sql        # users, outfits, tryon_jobs
├── ARCHITECTURE.md
└── README.md
```

Capas del backend: `main.py` (HTTP) → `jobs.py` (lógica) → `pipeline.py` (lógica pura) → `services/*` (acceso a datos y proveedores). Ninguna llamada a Supabase/R2/Replicate fuera de `services/`.

---

## 3. Endpoints del backend

| Método | Ruta | Body / Query | Respuesta | Notas |
|---|---|---|---|---|
| `GET` | `/health` | — | `{"status":"ok","missing_env":[],"storage":true,"database":true}` | Healthcheck de Railway y del CI |
| `POST` | `/tryon` | multipart: `image` (obligatorio), `person` (opcional), `description`, `user_id` | **202** `Job` | Crea job, sube originales a R2, arranca pipeline en background |
| `GET` | `/tryon/{id}` | — | `Job` | Estado actual |
| `GET` | `/tryon/{id}/events` | — | `text/event-stream` con un `Job` por cambio | Cierra al llegar a `done`/`error` |
| `GET` | `/results` | `user_id`, `limit` (≤100) | `{"items":[Job,…]}` | Historial del usuario |

Objeto `Job`:

```json
{
  "id": "3f2a…",
  "user_id": "7c1e…",
  "status": "processing",          // queued | processing | done | error
  "stage": "claude",               // queued | tryon | claude | refine | done | error
  "description": "vestido rojo satinado",
  "garment_url": "https://pub-xxx.r2.dev/jobs/3f2a…/garment.jpg",
  "person_url": null,
  "base_image_url": "https://pub-xxx.r2.dev/jobs/3f2a…/base.png",
  "improved_prompt": "Editorial studio photograph …",
  "final_image_url": "https://pub-xxx.r2.dev/jobs/3f2a…/final.jpg",
  "error": null,
  "created_at": "2026-08-26T20:00:00+00:00",
  "updated_at": "2026-08-26T20:01:40+00:00"
}
```

Errores: `400` tipo/imagen inválida o falta persona · `413` > 12 MB · `404` job inexistente · `500` faltan variables de entorno · fallos de IA quedan en `status:"error"` + `error` dentro del job (no rompen la petición).

---

## 4. Configuración Vercel

`frontend/vercel.json` ya incluido (framework `nextjs`, región `iad1`, cabeceras de seguridad).

Proyecto en Vercel:

1. https://vercel.com/new → Import Git Repository → seleccionar el repo.
2. **Root Directory** → `frontend`. Framework preset: Next.js (auto).
3. **Environment Variables** → `NEXT_PUBLIC_API_URL` = URL pública de Railway (sin barra final). Marcar Production + Preview.
4. **Deploy**.
5. Para que solo GitHub Actions despliegue (y no también el trigger nativo de Vercel): Settings → Git → **Ignored Build Step** → Command: `exit 0`.

Para el workflow (sección 6) necesitas tres valores:

| Secreto en GitHub | Dónde obtenerlo |
|---|---|
| `VERCEL_TOKEN` | https://vercel.com/account/tokens → Create |
| `VERCEL_ORG_ID` | Vercel → Settings → General → "Team ID" (o tu user ID) |
| `VERCEL_PROJECT_ID` | Proyecto → Settings → General → "Project ID" |

---

## 5. Configuración Railway (backend)

`backend/railway.json` + `backend/Dockerfile` ya incluidos.

1. https://railway.app/new → **Deploy from GitHub repo** → seleccionar el repo.
2. Service → Settings → **Root Directory** = `backend`. Builder: Dockerfile (auto por `railway.json`).
3. Settings → Networking → **Generate Domain** → copiar (`https://tryon-api-production.up.railway.app`).
4. **Variables** → pegar todo el contenido de `backend/.env.example` con valores reales (Raw Editor). `PORT` lo inyecta Railway; no hace falta ponerlo.
5. Settings → Deploy → Healthcheck path `/health` (ya viene de `railway.json`).
6. Para que despliegue GitHub Actions y no el trigger nativo: Settings → Source → desactivar **Auto Deploy** (opcional; si lo dejas, cada push despliega dos veces).

Valores para el workflow:

| Nombre | Tipo en GitHub | Dónde obtenerlo |
|---|---|---|
| `RAILWAY_TOKEN` | Secret | Railway → Project → Settings → Tokens → Create (project token) |
| `RAILWAY_SERVICE` | Variable | Nombre del servicio en Railway (ej. `tryon-api`) |
| `BACKEND_URL` | Variable | Dominio generado en el paso 3 |

Alternativas incluidas (mismo Dockerfile): `fly.toml` (`fly launch --copy-config`) y `render.yaml` (Blueprint). Solo Railway está cableado en `backend.yml`.

### Cloudflare R2

1. Cloudflare Dashboard → R2 → **Create bucket** `tryon`.
2. Bucket → Settings → **Public access** → Allow (R2.dev subdomain) → copiar `https://pub-xxxx.r2.dev` → `S3_PUBLIC_BASE_URL`.
3. R2 → **Manage R2 API Tokens** → Create → permiso Object Read & Write → copiar Access Key / Secret → `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`.
4. `S3_ENDPOINT_URL` = `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` (Account ID visible en la página de R2).
5. Subir la foto de modelo por defecto al bucket (`models/default.jpg`) → `DEFAULT_PERSON_IMAGE_URL` = `https://pub-xxxx.r2.dev/models/default.jpg`.

### Supabase (opcional)

1. https://supabase.com → New project.
2. SQL Editor → pegar `supabase/schema.sql` → Run.
3. Settings → API → `Project URL` → `SUPABASE_URL`; `service_role` key → `SUPABASE_SERVICE_KEY`.
4. Sin estas dos variables el backend funciona igual con almacenamiento en memoria (se pierde al redeploy).

---

## 6. GitHub Actions

Archivos: `.github/workflows/backend.yml` y `.github/workflows/frontend.yml` (contenido completo en el repo).

Secrets y variables a crear en GitHub → repo → Settings → Secrets and variables → Actions:

| Tipo | Nombre | Uso |
|---|---|---|
| Secret | `RAILWAY_TOKEN` | deploy backend |
| Secret | `VERCEL_TOKEN` | deploy frontend |
| Secret | `VERCEL_ORG_ID` | deploy frontend |
| Secret | `VERCEL_PROJECT_ID` | deploy frontend |
| Variable | `RAILWAY_SERVICE` | nombre del servicio Railway |
| Variable | `BACKEND_URL` | URL pública del backend (smoke test + `NEXT_PUBLIC_API_URL` en build) |

Comportamiento:

- `push` a `main` tocando `backend/**` → pytest → docker build → `railway up` → espera hasta 5 min a que `/health` responda `ok`.
- `push` a `main` tocando `frontend/**` → `npm ci && next build` → `vercel deploy --prod`.
- `pull_request` → tests/build + deploy de **preview** en Vercel (URL única por PR).
- Cambios en ambos directorios lanzan ambos workflows en paralelo.
- `concurrency` cancela runs obsoletos si se hacen varios push seguidos.

---

## 7. Flujo completo de datos

```
1. Navegador móvil
   └─ selecciona prenda.jpg (+ persona.jpg) → FormData → POST https://api/tryon
2. Backend main.py
   ├─ valida tipo/tamaño
   ├─ jobs.create_job(): sube garment/person a R2 → inserta fila tryon_jobs {status: queued}
   └─ responde 202 {id, status:"queued"}                                         (~1 s)
3. Navegador
   └─ abre EventSource /tryon/{id}/events (fallback: GET /tryon/{id} cada 2.5 s)
4. Backend BackgroundTask jobs.process_job()
   ├─ stage=tryon   → Replicate IDM-VTON(garment, person)    → URL temporal   (40–120 s)
   │                → storage.mirror_url() copia a R2 jobs/{id}/base.png
   ├─ stage=claude  → Claude ve base.png + descripción       → improved_prompt (3–8 s)
   ├─ stage=refine  → Replicate FLUX img2img(base, prompt)   → URL temporal   (15–40 s)
   │                → storage.mirror_url() copia a R2 jobs/{id}/final.jpg
   └─ update tryon_jobs {status: done, base_image_url, improved_prompt, final_image_url}
5. SSE emite el Job actualizado en cada cambio de stage → UI muestra progreso por etapas
6. status=done → UI renderiza final.jpg desde R2 (CDN), toggle base/refinada, prompt
7. GET /results?user_id → historial del usuario (Supabase) → grid "Tus looks"
```

Persistencia: originales, base y final viven en R2 (URLs permanentes; las de Replicate caducan en ~1 h). Metadatos en Supabase. El navegador solo habla con el backend; nunca con R2/Supabase/Replicate directamente, así las keys nunca salen del servidor.

Escalado: Railway → aumentar `numReplicas` en `railway.json` (los jobs son stateless si Supabase está activo); Replicate escala GPU por petición; R2 y Vercel son CDN globales. Siguiente paso cuando haya carga real: mover `process_job` a una cola (Railway worker + Redis/Upstash) manteniendo la misma API.

Costes por try-on: IDM-VTON ≈ $0.03–0.06 · FLUX dev ≈ $0.025 · Claude ≈ $0.005 · R2 ≈ $0 (10 GB gratis). Total ≈ $0.06–0.09.

---

## 8. Puesta en marcha sin Mac (orden exacto)

1. Crear repo en GitHub (web) → subir el contenido de `tryon-cloud/` (Upload files, o GitHub Codespaces + `git push`).
2. Cloudflare R2 (sección 5) → bucket, token, URL pública, foto de modelo.
3. Supabase (opcional) → schema.sql, URL, service key.
4. Railway (sección 5) → conectar repo, root `backend`, variables, dominio. Esperar primer deploy → abrir `https://<dominio>/health` → `"status":"ok"`.
5. Vercel (sección 4) → conectar repo, root `frontend`, `NEXT_PUBLIC_API_URL`. Esperar deploy → abrir la URL en el móvil.
6. Railway → Variables → `CORS_ORIGINS` = URL de Vercel (sin barra final). Redeploy.
7. GitHub → Secrets/Variables (sección 6).
8. Prueba end-to-end desde el móvil: prenda → Generar look → progreso 3 etapas → imagen final. Verificar en Railway → Logs `job … done`, en R2 la carpeta `jobs/{id}/`, en Supabase la fila en `tryon_jobs`.
9. Hacer un cambio trivial en `frontend/app/page.tsx` y otro en `backend/main.py` → `git push` → ver los dos workflows en verde en Actions → cambios visibles en producción.
