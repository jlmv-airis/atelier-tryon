# Atelier Virtual Try-On — Stack 100% gratuito (sin tarjeta)

Uso personal, un solo usuario. Todo en cloud, deploy con `git push`, cero coste.

```
Móvil (Safari/Chrome) ── Vercel Hobby (Next.js) ── Render Free (FastAPI, Docker)
                                                        │
                    ┌───────────────────────────────────┼──────────────────────────┐
                    ▼                                   ▼                          ▼
        Hugging Face (gratis, HF_TOKEN)        Supabase Free                GitHub Actions (gratis)
        ① Space yisol/IDM-VTON  → try-on       Postgres: tryon_jobs         test → docker → deploy
        ② Qwen3.5-9B (Inference) → prompt        Storage: bucket "tryon"     bootstrap · e2e · keepalive
        ③ FLUX.2-klein-4B (Inference) → refinado  (imágenes públicas)
```

Comportamiento del pipeline gratuito:

- **Try-on** corre en el Space público de IDM-VTON (ZeroGPU). Hay cola: 1–5 min según carga. Con `HF_TOKEN` la cuota diaria es mayor que anónimo.
- **Prompt**: LLM abierto con visión (`Qwen/Qwen3.5-9B`) vía Inference API, con modo *thinking* desactivado. Al prompt se le añade siempre un sufijo de consistencia (misma persona, cuerpo entero, misma pose y fondo). Si falla, se usa un prompt editorial fijo y el job continúa.
- **Refinado**: edición de imagen con `black-forest-labs/FLUX.1-Kontext-dev` vía Inference API (créditos mensuales gratuitos, limitados). Si falla o se agota la cuota, el job termina en `done` con la imagen base (`refined:false`). Poner `REFINE_REQUIRED=true` para que sea obligatorio.
- **Claude** queda desactivado salvo que exista `ANTHROPIC_API_KEY` (de pago).
- **Render Free** duerme tras 15 min sin uso; el primer request tarda ~50 s. `keepalive.yml` lo mantiene despierto de 06:00 a 24:00 (hora CDMX).

---

## 1. Cuentas necesarias (todas gratis, ninguna pide tarjeta)

| Servicio | Crear en | Qué obtener |
|---|---|---|
| GitHub | github.com | Fine-grained token (ver §2) |
| Hugging Face | huggingface.co/join | Settings → Access Tokens → New token (**Read**) → `HF_TOKEN` |
| Supabase | supabase.com | Proyecto `atelier` → Settings → API: `Project URL`, `service_role`; Settings → Database → contraseña de la base de datos → `SUPABASE_DB_PASSWORD` |
| Render | render.com (login con GitHub) | Account Settings → API Keys → `RENDER_API_KEY`; servicio → URL `srv-...` en la barra → `RENDER_SERVICE_ID` |
| Vercel | vercel.com (login con GitHub) | Importar el repo con Root Directory `frontend` y `NEXT_PUBLIC_API_URL`; despliega solo en cada push |

---

## 2. Orden exacto

### A. GitHub (lo hago yo con tu token)

1. Token: github.com → Settings → Developer settings → Personal access tokens → Fine-grained → Generate. Repository access: All. Permissions (Repository): **Administration RW, Contents RW, Actions RW, Secrets RW, Variables RW, Workflows RW**.
2. Con el token: creo `atelier-tryon`, subo el código, activo Actions.

### B. Hugging Face

3. Crear cuenta → Settings → Access Tokens → New token → tipo **Read** → copiar `hf_...`.
4. Abrir https://huggingface.co/spaces/yisol/IDM-VTON una vez logueado (acepta el uso del Space si lo pide).

### C. Supabase

5. New project `atelier` (guardar contraseña de la DB) → esperar "Active".
6. Settings → API → copiar `Project URL` y `service_role`.
7. Settings → Database → contraseña de la base de datos (la que generaste al crear el proyecto) → `SUPABASE_DB_PASSWORD`.
   (El schema y el bucket los crea el bootstrap; no tocar SQL Editor ni Storage a mano.)

### D. Render

8. render.com → New → **Blueprint** → conectar repo `atelier-tryon` → detecta `render.yaml` → Apply. Servicio `tryon-api`, plan Free.
9. Primer deploy fallará el healthcheck (sin variables): esperado.
10. Copiar URL pública `https://tryon-api-xxxx.onrender.com` → `BACKEND_URL`.
11. Servicio → la URL del navegador contiene `srv-xxxxxxxx` → `RENDER_SERVICE_ID`. Account Settings → API Keys → Create → `RENDER_API_KEY`.

### E. Vercel

12. vercel.com/new → Import `atelier-tryon` → Root Directory `frontend` → Deploy (aunque aún no conecte).
13. Copiar URL `https://atelier-tryon.vercel.app` → `FRONTEND_URL`. Settings → General → `Project ID`; Team Settings → `Team ID` (= `VERCEL_ORG_ID`).
14. Dejar la integración Git de Vercel activa: despliega sola en cada push a `main` (no configurar Ignored Build Step).

### F. Secrets y variables en GitHub (los pegas tú, no por el chat)

Repo → Settings → Secrets and variables → Actions:

| Secrets | Variables |
|---|---|
| `HF_TOKEN` | `BACKEND_URL` |
| `SUPABASE_URL` | `FRONTEND_URL` |
| `SUPABASE_SERVICE_KEY` | |
| `SUPABASE_DB_PASSWORD` (contraseña de la DB, sin codificar) | `SUPABASE_DB_HOST` (opcional; default pooler us-east-1) |
| `RENDER_API_KEY` | |
| `RENDER_SERVICE_ID` | |

### G. Bootstrap y verificación (lo lanzo yo por la API de GitHub)

16. Workflow **Bootstrap** → crea bucket, genera `models/default.jpg` con FLUX (artefacto descargable para verla), aplica schema, carga variables en Render y despliega el backend. El frontend lo despliega Vercel en cada push.
17. Workflow **E2E** → try-on real con `assets/prenda-test.jpg` → artefacto con `base.png`, `final.jpg`, `job.json`.
18. Prueba desde tu móvil (sección 3).

---

## 3. Prueba desde móvil

| Etapa | UI | Tiempo (gratis) |
|---|---|---|
| `queued` | "En cola" | < 2 s (hasta 50 s si Render estaba dormido) |
| `tryon` | "Try-on con IA", barra 1 | 1–5 min (cola ZeroGPU) |
| `claude` | "Análisis editorial" | 5–20 s |
| `refine` | "Refinado hiperrealista" | 20–60 s, o se omite si la cuota se agotó |
| `done` | Imagen final + Refinada/Base + prompt | — |

---

## 4. Errores propios del stack gratuito

| Síntoma | Causa | Fix |
|---|---|---|
| `error`: `You have exceeded your GPU quota` | Cuota ZeroGPU agotada | Esperar el tiempo indicado en el mensaje; confirmar que `HF_TOKEN` está en Render |
| `error`: `Space is sleeping` / `paused` | Space público apagado | Abrir https://huggingface.co/spaces/yisol/IDM-VTON en el navegador (lo despierta) y reintentar |
| `error`: `The Space no devolvio un archivo` | Cambió la API del Space | Ver "Use via API" en la página del Space → ajustar `HF_TRYON_API_NAME` o el orden de argumentos en `services/hf_client.py::tryon` |
| `done` con `refined:false` siempre | Inference API sin créditos o modelo no disponible en el proveedor gratuito | Aceptable. Alternativa: `HF_REFINE_MODEL` a otro modelo img2img disponible; o `AI_PROVIDER=replicate` (pago) |
| Prompt siempre es el fijo (`Editorial fashion photograph of the same model…`) | LLM de Inference no disponible | Cambiar `HF_LLM_MODEL` / `HF_LLM_TEXT_MODEL` a un modelo listado en https://huggingface.co/inference/models |
| Primer request tarda ~50 s | Render Free dormido | Normal; `keepalive.yml` activo lo evita en horario |
| `502` en Render durante minutos | Render Free reiniciando por límite de memoria (512 MB) | Reintentar; no correr más de un job a la vez |
| `storage:false` en `/health` | Faltan `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` | Bootstrap de nuevo |
| `Bucket not found` | No se ejecutó el bootstrap | Workflow Bootstrap |

---

## 5. Estado verificado (27-ago-2026)

- Repo `jlmv-airis/atelier-tryon`; backend `https://tryon-api-q16h.onrender.com`; web `https://atelier-tryon-hazel.vercel.app`.
- Bootstrap, backend CI/CD (push→deploy) y E2E en verde. E2E #3: try-on + prompt LLM + refinado en 1m17s.
- Entrada: cualquier formato de imagen (HEIC de iPhone incluido) se normaliza a JPEG 1024px.
- Secrets no usados que se pueden borrar: `SUPABASE_DB_URL`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.

## 6. Criterio de "funcionando" (uso personal)

1. `/health` → `{"status":"ok","missing_env":[],"storage":true,"database":true,"ai_provider":"hf","prompt_provider":"hf"}`.
2. Bootstrap y E2E en verde; artefacto `default-model` muestra una mujer de cuerpo completo 3:4 sobre fondo liso.
3. Desde el móvil: 2 generaciones seguidas en `done` con imagen visible, y "Tus looks" persiste tras cerrar el navegador.
4. Un push a `main` despliega solo (workflows en verde por `push`).
5. Coste total: 0 USD.
