# DEPLOY OPERATOR — Atelier Virtual Try-On

Ejecución lineal. Cada paso tiene una condición **NO ANTES DE** que bloquea el avance.
Detalle clic a clic de cada servicio: `GO-LIVE.md` (mismos números de paso).

---

## 1. CHECKLIST DE EJECUCIÓN FINAL (LINEAL)

### Fase 0 — Prerrequisitos

1. Billing activo en Replicate, Anthropic, Cloudflare, Railway (Hobby).
   **NO ANTES DE:** nada. Es el punto de partida.
2. Tener `default.jpg` (modelo cuerpo entero 3:4) y `prenda-test.jpg`.
   **NO crear ningún servicio hasta tener estos dos archivos.**

### Fase 1 — GitHub

3. Crear repo privado `atelier-tryon` y subir `tryon-cloud/` completo (incluida `.github/`).
   **NO ANTES DE:** paso 2.
4. Actions → confirmar `Tests` ✔ `Docker build check` ✔ `Build` ✔ (los jobs `Deploy` fallan: esperado).
   **NO configurar secrets todavía.** Sin Railway/Vercel creados no existen los valores.

### Fase 2 — R2

5. Bucket `tryon` → Public access ON → subir `models/default.jpg` → crear API token Object Read & Write → anotar Account ID.
   **NO ANTES DE:** paso 4.
6. Abrir `https://pub-xxxx.r2.dev/models/default.jpg` desde el móvil → se ve la foto.
   **NO pasar a Supabase si esta URL no abre.** Todo el pipeline depende de ella.

### Fase 3 — Supabase

7. Proyecto `atelier` → SQL Editor → ejecutar `supabase/schema.sql` → anotar Project URL + service_role.
   **NO ANTES DE:** paso 6.
8. Table Editor → `tryon_jobs` existe.
   **NO usar la key `anon`.** El backend requiere `service_role`.

### Fase 4 — Railway

9. Deploy from GitHub → servicio `tryon-api` → Root Directory `backend` → Generate Domain (puerto 8000).
   **NO ANTES DE:** paso 8 (necesitas todas las variables listas).
10. Variables (Raw Editor) → las 14 de `GO-LIVE.md` paso 19 con `CORS_ORIGINS=*`.
    **NO hacer deploy manual antes de pegar las variables**: arrancaría con `missing_env` y el healthcheck fallaría.
11. Deployment **Active** → `/health` → `{"status":"ok","missing_env":[],"storage":true,"database":true}`.
    **NO avanzar con cualquier `false` o `missing_env` no vacío.**
12. `/docs` → `POST /tryon` con `prenda-test.jpg` → 202 → `/tryon/<id>` hasta `done` → `final_image_url` empieza por `https://pub-`.
    **NO crear Vercel hasta tener un job real en `done` con URL de R2.** Si falla aquí, es backend/IA, no frontend.

### Fase 5 — Vercel

13. Import repo → Root `frontend` → env `NEXT_PUBLIC_API_URL=https://<dominio-railway>` → Deploy → anotar URL, Project ID, Team ID.
    **NO ANTES DE:** paso 12.
14. Settings → Git → Ignored Build Step `exit 0`.
    **NO dejar el auto-deploy de Vercel activo**: desplegaría dos veces y con env potencialmente distinta al workflow.
15. Railway → `CORS_ORIGINS=https://<url-vercel>` → Active.
    **NO dejar `*` en producción.**
16. Abrir la web en PC → "Backend activo" verde.
    **NO probar en móvil todavía**: primero confirmar CORS cerrado desde PC con consola abierta (F12 sin errores CORS).

### Fase 6 — GitHub Actions

17. Secrets: `RAILWAY_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`. Variables: `RAILWAY_SERVICE=tryon-api`, `BACKEND_URL=https://<dominio-railway>`.
    **NO ANTES DE:** paso 16.
18. Railway → Source → Auto Deploy OFF.
    **NO hacer push antes de esto**: dos deploys simultáneos del mismo commit.
19. Run workflow manual `Backend` → 3 jobs ✔. Run workflow manual `Frontend` → 2 jobs ✔.
20. Push de prueba (cambio de texto en `frontend/app/page.tsx`) → workflow frontend ✔ → cambio visible en la web.
    **NO declarar CI/CD funcionando con runs manuales**: el criterio es un run disparado por push.

### Fase 7 — Móvil

21. Ejecutar la sección 3 completa desde un móvil.
    **NO ANTES DE:** paso 20.

---

## 2. VALIDACIÓN POR BLOQUE

### GitHub Actions

| | |
|---|---|
| Estado correcto | Último run de `Backend · test & deploy` y `Frontend · build & deploy` en verde, evento `push`, rama `main` |
| Señal OK | En `Deploy to Railway` el log termina en `healthy`; en `Deploy production` aparece `Production: https://…vercel.app` |
| Señal de fallo | `Tests` rojo = código roto (`backend/tests/test_api.py`) · `Deploy to Railway` rojo con `service not found` = `RAILWAY_SERVICE` mal · `backend no respondio a tiempo` = deploy arrancó pero `/health` no responde (ver Railway) · `Deploy production` rojo con `403`/`not found` = `VERCEL_ORG_ID`/`VERCEL_PROJECT_ID` mal |

### Vercel

| | |
|---|---|
| Estado correcto | Deployment **Ready** en Production, origen "GitHub Actions" (CLI), env `NEXT_PUBLIC_API_URL` definida en Production y Preview |
| Señal OK | La web carga en < 2 s, cabecera "Backend activo" verde, F12 → Network → `GET /health` 200 al dominio de Railway |
| Señal de fallo | "Backend no disponible" = env mal o CORS · pantalla en blanco = build roto (ver logs del deployment) · `GET http://localhost:8000/health` en Network = `NEXT_PUBLIC_API_URL` no estaba en el build |

### Railway

| | |
|---|---|
| Estado correcto | Deployment **Active**, healthcheck `/health` verde, 1 réplica, dominio en puerto 8000 |
| Señal OK | `/health` → `storage:true`, `database:true`, `missing_env:[]`; Logs muestran `Application startup complete` y, por job, `job <id> done -> https://pub-…` |
| Señal de fallo | **Crashed** = traceback al arrancar (variable mal, import roto) · **Sleeping** = plan Free · healthcheck rojo = puerto ≠ 8000 o app no arranca · `job <id> failed` en logs = fallo IA/storage (sección 4) |

### R2

| | |
|---|---|
| Estado correcto | Bucket `tryon` con Public access **Allowed**, token con permiso Object Read & Write sobre ese bucket |
| Señal OK | Tras un job: carpeta `jobs/<id>/` con `garment.jpg`, `base.png`, `final.jpg`; sus URLs `pub-…r2.dev` abren desde el móvil |
| Señal de fallo | `/health` → `storage:false` = falta alguna `S3_*` · `SignatureDoesNotMatch` / `InvalidAccessKeyId` en logs = token o endpoint mal · URL `pub-` da 404/403 = Public access OFF · `final_image_url` es `replicate.delivery` = storage inactivo (caduca en 1 h) |

### Supabase

| | |
|---|---|
| Estado correcto | Proyecto **Active**, tabla `tryon_jobs` con RLS habilitado, backend usando `service_role` |
| Señal OK | `/health` → `database:true`; una fila nueva por job con `status` avanzando hasta `done`; "Tus looks" persiste tras reabrir el navegador |
| Señal de fallo | `database:false` = faltan `SUPABASE_*` · `401`/`permission denied` en logs = se usó key `anon` · `relation "tryon_jobs" does not exist` = no se ejecutó `schema.sql` · historial vacío tras redeploy = backend en memoria |

---

## 3. PRUEBA END-TO-END REAL (MÓVIL)

22. Móvil → navegador → `https://<url-vercel>`.
23. Cabecera: **Backend activo** (verde).
24. Tocar **Prenda** → elegir foto → miniatura visible. Dejar **Tu foto** vacío.
25. Escribir `blusa blanca de seda` → tocar **Generar look**.

| Etapa | Qué se ve en la UI | Tiempo | Railway Logs |
|---|---|---|---|
| `queued` | Botón "Enviando…" → tarjeta **Creando tu look**, texto "En cola", 3 barras grises | < 2 s | `"POST /tryon HTTP/1.1" 202 Accepted` |
| `tryon` | Texto "Try-on con IA", barra 1 parpadeando | 40–120 s (hasta 3 min en cold start) | — |
| `claude` | Texto "Análisis editorial (Claude)", barra 1 fija negra, barra 2 parpadeando | 3–10 s | — |
| `refine` | Texto "Refinado hiperrealista", barras 1–2 fijas, barra 3 parpadeando | 15–40 s | — |
| `done` | Imagen 3:4 a pantalla completa, badge **Editorial**, segmento **Refinada / Base**, tarjeta **Dirección de arte (Claude)** con el prompt, botones **Abrir / Nuevo look** | — | `job <id> done -> https://pub-…/jobs/<id>/final.jpg` |
| `error` | Tarjeta roja "No se pudo generar el look. <mensaje>" + botón **Intentar de nuevo** | — | `job <id> failed` + traceback |

26. Tocar **Base** → imagen sin refinar. Tocar **Refinada** → imagen final.
27. Tocar **Abrir** → pestaña nueva con URL `pub-…r2.dev`.
28. Tocar **Nuevo look** → inicio + sección **Tus looks** con la miniatura.
29. Cerrar navegador, reabrir URL → **Tus looks** sigue ahí.
30. Repetir 24–28 dos veces más (3 generaciones en total).

---

## 4. DEBUG FINAL

### 4.1 Backend no responde (`/health` no carga o web dice "Backend no disponible")

| Causa exacta | Archivo probable | Fix directo |
|---|---|---|
| Servicio **Crashed** por variable mal escrita (`int()`/`float()` de un valor no numérico) | `backend/config.py` | Railway → Variables → corregir `DIFFUSION_STEPS`, `DIFFUSION_GUIDANCE`, `JOB_TTL_SECONDS`, `PORT` (solo números) → Redeploy |
| Healthcheck falla por puerto | `backend/Dockerfile` (`PORT`) / Railway Networking | Dominio al puerto **8000**; no definir `PORT` a mano en Railway |
| `missing_env` no vacío | Railway Variables | Añadir `REPLICATE_API_TOKEN` / `ANTHROPIC_API_KEY` → Redeploy |
| Servicio dormido | Plan Railway | Upgrade a Hobby |
| Root Directory incorrecto (build falla con `requirements.txt not found`) | Railway → Settings → Source | Root Directory = `backend` |

### 4.2 Job se queda en `tryon`

| Causa exacta | Archivo probable | Fix directo |
|---|---|---|
| Cold start GPU de IDM-VTON (predicción en `starting`) | — | Esperar hasta 6 min. https://replicate.com/predictions |
| Job realmente falló pero la UI no refresca | `backend/jobs.py` (`process_job` escribe `error`) | Abrir `/tryon/<id>` → leer `error` → tabla siguiente |
| `422 Invalid input` de IDM-VTON | `backend/services/replicate_client.py` (`call_tryon_model`) | Sustituir `models/default.jpg` por foto cuerpo entero 3:4 fondo liso; o `TRYON_CATEGORY=dresses` si la prenda es vestido |
| `404 version not found` | `backend/config.py` (`TRYON_MODEL`) | Variable `TRYON_MODEL=cuuupid/idm-vton:<hash actual>` |
| `401` / `402` Replicate | Railway Variables | Token nuevo / cargar saldo |
| Railway reinició a mitad del job (log `Application startup complete` en medio) | `backend/jobs.py` (BackgroundTasks in-process) | Redeploy no debe hacerse con jobs activos; reintentar el job. Si es frecuente: `numReplicas` sigue en 1 y subir memoria del servicio |

### 4.3 No llega imagen final (`done` sin imagen, o `error` en `refine`)

| Causa exacta | Archivo probable | Fix directo |
|---|---|---|
| `final_image_url` es `replicate.delivery` y ya caducó | `backend/services/storage.py` (`mirror_url` inactivo) | Completar las 5 `S3_*` → `/health` → `storage:true` |
| URL `pub-…` devuelve 403/404 | R2 bucket Settings | Public access → Allow |
| `SignatureDoesNotMatch` / `InvalidAccessKeyId` | `backend/services/storage.py` (`_client`) | Regenerar token R2; `S3_ENDPOINT_URL` con el Account ID correcto; `S3_REGION=auto` |
| `error` en `call_diffusion` con `422` | `backend/services/replicate_client.py` (`call_diffusion`) | `DIFFUSION_PROMPT_STRENGTH=0.4`, reintentar |
| `Claude no devolvio texto` / `Could not process image` | `backend/services/claude_client.py` (`call_claude`) | Confirmar que `base_image_url` abre públicamente (R2 público); `CLAUDE_MODEL` válido |
| Imagen carga en `/tryon/<id>` pero no en la web | `frontend/next.config.mjs` (`remotePatterns`) — no aplica a `<img>` nativo; entonces es caché | Vercel → Redeploy; hard refresh en móvil |

### 4.4 SSE no actualiza (barras no avanzan)

| Causa exacta | Archivo probable | Fix directo |
|---|---|---|
| Proxy cierra el stream → la web pasa sola a polling 2,5 s | `frontend/lib/api.ts` (`subscribeToJob` → `poll`) | Ninguno; esperar. Verificar en `/tryon/<id>` que `stage` avanza |
| Ni SSE ni polling avanzan | `backend/jobs.py` (`_set_stage`) / Supabase | `/health` → `database:true`; si `false`, el store en memoria se pierde al reiniciar → completar `SUPABASE_*` |
| `404 Job no encontrado` al abrir `/events` | `backend/services/db.py` | Backend reiniciado con store en memoria → completar `SUPABASE_*` y reintentar |
| `EventSource` bloqueado por CORS | Railway `CORS_ORIGINS` | Poner la URL exacta de Vercel (https, sin barra final) |

### 4.5 Vercel no conecta con backend

| Causa exacta | Archivo probable | Fix directo |
|---|---|---|
| `NEXT_PUBLIC_API_URL` ausente en el build (Network muestra `localhost:8000`) | `frontend/lib/api.ts` (`API_URL`) + GitHub Variable `BACKEND_URL` | Definir `BACKEND_URL` en GitHub Variables y `NEXT_PUBLIC_API_URL` en Vercel → Redeploy |
| URL con barra final o `http://` | Vercel env | `https://<dominio>` exacto, sin `/` final |
| Error CORS en consola | `backend/main.py` (`CORSMiddleware`) ← `CORS_ORIGINS` | `CORS_ORIGINS=https://<url-vercel>` exacta; varios dominios separados por coma sin espacios |
| Mixed content (web https → backend http) | Railway Networking | Usar siempre el dominio `https://…up.railway.app` |
| Web desplegada por Vercel nativo con env vieja | Vercel → Git | Ignored Build Step `exit 0`; redeploy desde GitHub Actions |

---

## 5. CRITERIO FINAL DE PRODUCCIÓN

Listo para usuarios reales cuando los 12 puntos se cumplen el mismo día, sin tocar nada entre ellos:

31. `/health` → `{"status":"ok","missing_env":[],"storage":true,"database":true}`.
32. Railway → último deployment **Active** creado por GitHub Actions; Auto Deploy OFF.
33. Vercel → último deployment **Ready** creado por GitHub Actions; Ignored Build Step activo.
34. Actions → últimos runs de ambos workflows en verde disparados por **push**.
35. `CORS_ORIGINS` = URL de Vercel exacta (no `*`) y la web muestra "Backend activo".
36. **3 generaciones consecutivas desde móvil** en `done`, cada una < 4 min, sin ningún `error`.
37. Las 6 URLs (base + final × 3) empiezan por `S3_PUBLIC_BASE_URL` y abren **1 hora después**.
38. Supabase `tryon_jobs` → 3 filas `done`; "Tus looks" persiste tras cerrar y reabrir el navegador.
39. R2 → 3 carpetas `jobs/<id>/` con `garment.jpg`, `base.png`, `final.jpg`.
40. Railway Logs → 3 líneas `job <id> done`, **cero** `job <id> failed`, cero `Traceback`.
41. Replicate Predictions → 6 predicciones `succeeded` (2 por job); Anthropic Usage → 3 requests.
42. Prueba de resiliencia: Railway → Redeploy → tras **Active**, una 4ª generación desde móvil termina en `done` y "Tus looks" muestra las 4.

Cualquier punto sin cumplir → sistema NO en producción → sección 4.
