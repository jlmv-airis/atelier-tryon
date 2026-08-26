# GO-LIVE — Atelier Virtual Try-On

Orden fijo: GitHub → R2 → Supabase → Railway → Vercel → GitHub Actions → prueba móvil.
No avanzar de bloque sin cumplir su punto de verificación.

---

## 1. CHECKLIST PREVIO AL PRIMER DEPLOY

### 1.1 Cuentas con billing activo (sin esto el pipeline falla en el primer job)

1. Replicate → https://replicate.com/account/billing → tarjeta añadida.
2. Anthropic → https://console.anthropic.com → Billing → saldo ≥ 5 USD.
3. Cloudflare → cuenta creada (R2 tiene 10 GB gratis, requiere tarjeta para activar R2).
4. Railway → plan Hobby (5 USD/mes) activado; el plan gratuito duerme el servicio.
5. Vercel → plan Hobby (gratis) suficiente.
6. Supabase → plan Free suficiente.

### 1.2 Assets obligatorios

7. `default.jpg`: foto de modelo, cuerpo entero, de frente, fondo liso, 768×1024 (3:4), < 2 MB.
8. `prenda-test.jpg`: foto de producto de una prenda superior sobre fondo blanco (para la prueba final).

### 1.3 Variables críticas del sistema

| Variable | Dónde vive | Sin ella |
|---|---|---|
| `REPLICATE_API_TOKEN` | Railway | `/health` la lista en `missing_env`; `/tryon` → 500 |
| `ANTHROPIC_API_KEY` | Railway | Igual |
| `DEFAULT_PERSON_IMAGE_URL` | Railway | `/tryon` sin foto de persona → 400 |
| `S3_ENDPOINT_URL` `S3_ACCESS_KEY_ID` `S3_SECRET_ACCESS_KEY` `S3_BUCKET` `S3_PUBLIC_BASE_URL` | Railway | `/health` → `"storage": false`; las imágenes usan URLs de Replicate que **caducan en 1 h** |
| `SUPABASE_URL` `SUPABASE_SERVICE_KEY` | Railway | `/health` → `"database": false`; historial se pierde en cada redeploy |
| `CORS_ORIGINS` | Railway | El navegador bloquea la llamada: "Backend no disponible" en la web |
| `NEXT_PUBLIC_API_URL` | Vercel + GitHub Variable `BACKEND_URL` | La web apunta a `localhost:8000` → nunca conecta |
| `RAILWAY_TOKEN` `VERCEL_TOKEN` `VERCEL_ORG_ID` `VERCEL_PROJECT_ID` | GitHub Secrets | Los workflows fallan en el paso de deploy |
| `RAILWAY_SERVICE` `BACKEND_URL` | GitHub Variables | `railway up` no encuentra el servicio / smoke test falla |

---

## 2. ORDEN FINAL DE DEPLOY

### BLOQUE A — GitHub

1. https://github.com/new → nombre `atelier-tryon` → **Private** → Create.
2. **Add file → Upload files** → arrastrar TODO el contenido de `tryon-cloud/` (carpetas `.github`, `backend`, `frontend`, `supabase` y archivos raíz) → Commit.
3. Verificar en el repo: existe `.github/workflows/backend.yml`, `backend/Dockerfile`, `frontend/package.json`.
4. Actions → los dos workflows habrán corrido y **fallado en el paso deploy** (faltan secrets). Es lo esperado. Los jobs `Tests`, `Docker build check` y `Build` deben estar en **verde**.

✅ Verificación A: `Tests` ✔ `Docker build check` ✔ `Build` ✔.

### BLOQUE B — Cloudflare R2

5. Dashboard → **R2 Object Storage** → Create bucket → nombre `tryon` → Location: Automatic → Create.
6. Bucket `tryon` → **Settings** → Public access → **R2.dev subdomain** → Allow Access → copiar `https://pub-xxxxxxxx.r2.dev`.
7. Bucket → **Objects** → Upload → crear carpeta `models` → subir `default.jpg`.
8. Abrir en el navegador `https://pub-xxxxxxxx.r2.dev/models/default.jpg` → debe mostrar la foto.
9. R2 → **Manage R2 API Tokens** → Create API token → Permissions: **Object Read & Write** → Specify bucket: `tryon` → Create → copiar **Access Key ID** y **Secret Access Key** (solo se muestran una vez).
10. Copiar el **Account ID** (aparece en la página de R2, columna derecha).

Anotar:

```
S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=<access key>
S3_SECRET_ACCESS_KEY=<secret>
S3_BUCKET=tryon
S3_REGION=auto
S3_PUBLIC_BASE_URL=https://pub-xxxxxxxx.r2.dev
DEFAULT_PERSON_IMAGE_URL=https://pub-xxxxxxxx.r2.dev/models/default.jpg
```

✅ Verificación B: la URL del paso 8 abre la foto desde el móvil.

### BLOQUE C — Supabase

11. https://supabase.com/dashboard → New project → nombre `atelier` → contraseña DB (guardar) → región más cercana → Create. Esperar 2 min.
12. **SQL Editor** → New query → pegar el contenido completo de `supabase/schema.sql` → **Run** → "Success. No rows returned".
13. **Table Editor** → deben existir `users`, `outfits`, `tryon_jobs`.
14. **Project Settings → API** → copiar **Project URL** y la key **service_role** (sección "Project API keys", pulsar Reveal).

Anotar:

```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service_role>
```

✅ Verificación C: tabla `tryon_jobs` visible con 14 columnas.

### BLOQUE D — Railway (backend)

15. https://railway.app/new → **Deploy from GitHub repo** → autorizar → seleccionar `atelier-tryon` → Deploy Now.
16. Clic en el servicio creado → **Settings** → renombrar a `tryon-api`.
17. Settings → **Source** → Root Directory: `backend` → guardar.
18. Settings → **Networking** → Generate Domain → puerto `8000` → copiar `https://tryon-api-production-xxxx.up.railway.app`.
19. **Variables** → **Raw Editor** → pegar exactamente (rellenar valores):

```
REPLICATE_API_TOKEN=r8_...
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-5
DEFAULT_PERSON_IMAGE_URL=https://pub-xxxxxxxx.r2.dev/models/default.jpg
S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_BUCKET=tryon
S3_REGION=auto
S3_PUBLIC_BASE_URL=https://pub-xxxxxxxx.r2.dev
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=...
CORS_ORIGINS=*
JOB_TTL_SECONDS=86400
```

(`CORS_ORIGINS=*` es temporal; se cierra en el paso 30.)

20. Update Variables → Railway redespliega. **Deployments** → esperar estado **Active** (2–4 min).
21. Abrir `https://<dominio-railway>/health`:

```json
{"status":"ok","missing_env":[],"storage":true,"database":true}
```

22. Prueba real del backend desde el navegador: `https://<dominio-railway>/docs` → `POST /tryon` → Try it out → `image` = `prenda-test.jpg` → Execute → respuesta **202** con `"status":"queued"` → copiar `id`.
23. Abrir `https://<dominio-railway>/tryon/<id>` y recargar cada 20 s hasta `"status":"done"` (1–3 min). `final_image_url` debe empezar por `https://pub-xxxxxxxx.r2.dev/jobs/`.
24. Abrir `final_image_url` → imagen de la modelo con la prenda.

✅ Verificación D: `/health` con los tres `true`/vacío y un job real en `done` con URL de R2.

Si el paso 23 termina en `"status":"error"`, ir a la sección 4.2 antes de continuar.

### BLOQUE E — Vercel (frontend)

25. https://vercel.com/new → Import `atelier-tryon` → **Root Directory** → Edit → `frontend` → Continue.
26. Environment Variables → Name `NEXT_PUBLIC_API_URL` → Value `https://<dominio-railway>` (sin barra final) → Add.
27. **Deploy** → esperar "Congratulations" → copiar la URL `https://atelier-tryon.vercel.app`.
28. Settings → General → copiar **Project ID**. Settings (del equipo/usuario, arriba a la izquierda) → General → copiar **Team ID** (o User ID).
29. Settings → Git → **Ignored Build Step** → Command: `exit 0` → Save. (Vercel deja de desplegar por su cuenta; lo hará GitHub Actions.)
30. Railway → Variables → `CORS_ORIGINS=https://atelier-tryon.vercel.app` → Update → esperar **Active**.
31. Abrir `https://atelier-tryon.vercel.app` en el navegador del PC → arriba a la derecha debe decir **Backend activo** (punto verde).

✅ Verificación E: "Backend activo" en verde con `CORS_ORIGINS` ya cerrado.

### BLOQUE F — GitHub Actions (deploy automático)

32. Railway → Project → **Settings → Tokens** → Create token → nombre `github` → copiar.
33. Vercel → https://vercel.com/account/tokens → Create → nombre `github` → Scope: tu equipo → copiar.
34. GitHub → repo → **Settings → Secrets and variables → Actions**:

| Pestaña | Nombre | Valor |
|---|---|---|
| Secrets | `RAILWAY_TOKEN` | paso 32 |
| Secrets | `VERCEL_TOKEN` | paso 33 |
| Secrets | `VERCEL_ORG_ID` | Team/User ID (paso 28) |
| Secrets | `VERCEL_PROJECT_ID` | Project ID (paso 28) |
| Variables | `RAILWAY_SERVICE` | `tryon-api` |
| Variables | `BACKEND_URL` | `https://<dominio-railway>` |

35. Railway → servicio → Settings → Source → desactivar **Auto Deploy** (evita deploy doble).
36. GitHub → Actions → **Backend · test & deploy** → Run workflow → main → Run. Esperar: `Tests` ✔ `Docker build check` ✔ `Deploy to Railway` ✔ (incluye smoke test de `/health`).
37. Actions → **Frontend · build & deploy** → Run workflow → main → Run. Esperar: `Build` ✔ `Deploy production` ✔.
38. Prueba de push real: en GitHub, editar `frontend/app/page.tsx` → cambiar el texto `Pruébatelo antes de comprarlo.` por `Pruébatelo antes de comprarlo ✦` → Commit to main. Actions → workflow frontend en verde → recargar la web → texto cambiado.

✅ Verificación F: ambos workflows en verde lanzados por push, cambio visible en producción.

---

## 3. PRUEBA FINAL REAL DESDE MÓVIL

39. En el iPhone/Android abrir Safari/Chrome → `https://atelier-tryon.vercel.app`.
40. Cabecera: **Backend activo** (verde). Si dice "Backend no disponible" → sección 4.4.
41. Tocar **Prenda** → Fototeca → elegir la foto de la prenda → aparece la miniatura.
42. (Dejar **Tu foto** vacío para usar la modelo por defecto.)
43. Escribir descripción: `blusa blanca de seda`.
44. Tocar **Generar look**. Botón cambia a "Enviando…" < 2 s.

Qué esperar en cada etapa (tarjeta "Creando tu look" con 3 barras):

| Etapa | UI | Duración | Railway Logs |
|---|---|---|---|
| `queued` | "En cola", ninguna barra activa | < 2 s | `POST /tryon HTTP/1.1" 202` |
| `tryon` | "Try-on con IA", barra 1 parpadea | 40–120 s (primera vez hasta 3 min por cold start GPU) | — |
| `claude` | "Análisis editorial (Claude)", barra 1 fija, barra 2 parpadea | 3–10 s | — |
| `refine` | "Refinado hiperrealista", barras 1-2 fijas, barra 3 parpadea | 15–40 s | — |
| `done` | Imagen final a pantalla completa, badge **Editorial**, segmento Refinada/Base, tarjeta "Dirección de arte (Claude)" | — | `job <id> done -> https://pub-...r2.dev/jobs/<id>/final.jpg` |

45. Tocar **Base** → se ve la imagen sin refinar; tocar **Refinada** → vuelve la final.
46. Tocar **Abrir** → la imagen abre en pestaña nueva desde `pub-xxxx.r2.dev`.
47. Tocar **Nuevo look** → vuelve al inicio; abajo aparece la sección **Tus looks** con la miniatura.
48. Cerrar el navegador, volver a abrir la URL → **Tus looks** sigue mostrando el resultado (historial en Supabase).
49. Supabase → Table Editor → `tryon_jobs` → fila con `status = done` y las tres URLs.
50. Cloudflare R2 → bucket `tryon` → carpeta `jobs/<id>/` con `garment.jpg`, `base.png`, `final.jpg`.

---

## 4. VERIFICACIÓN DE ERRORES CRÍTICOS

### 4.1 No aparece imagen (job en `done` pero cuadro vacío)

1. Railway → Logs → buscar `job <id> done ->` → copiar la URL → abrirla en el móvil.
2. Si la URL no abre y es `pub-xxxx.r2.dev` → R2 → bucket → Settings → Public access debe estar **Allowed**. Si es `replicate.delivery` → storage no está activo: `/health` → `"storage": false` → revisar las 5 variables `S3_*` en Railway (paso 19) y redeploy.
3. Si la URL abre pero la web no la muestra → Vercel → Deployments → el último deploy debe ser posterior al último cambio de `NEXT_PUBLIC_API_URL`; si no, Redeploy.

### 4.2 Pipeline se queda en `tryon` o pasa a `error`

1. `https://<dominio-railway>/tryon/<id>` → leer campo `error`.
2. Railway → Logs → buscar `job <id> failed` → leer la última línea `File "..."`:

| Mensaje / línea | Causa | Acción |
|---|---|---|
| Sigue en `tryon` > 4 min sin `failed` | Cold start de IDM-VTON | Esperar hasta 6 min. https://replicate.com/predictions muestra `starting` |
| `in call_tryon_model` + `401` | Token Replicate inválido | Regenerar en Replicate, actualizar variable, redeploy |
| `in call_tryon_model` + `402` / `Insufficient credit` | Sin saldo Replicate | Billing |
| `in call_tryon_model` + `422` / `Invalid input` | Foto de modelo no válida | Sustituir `models/default.jpg` por una de cuerpo entero 3:4 fondo liso |
| `in call_tryon_model` + `404` / `version` | Versión IDM-VTON retirada | https://replicate.com/cuuupid/idm-vton/versions → copiar hash → variable `TRYON_MODEL=cuuupid/idm-vton:<hash>` |
| `in call_claude` + `authentication_error` | Key Anthropic inválida | Regenerar, actualizar, redeploy |
| `in call_claude` + `not_found_error` | `CLAUDE_MODEL` inexistente | Poner un modelo listado en console.anthropic.com |
| `in call_claude` + `Could not process image` | Claude no pudo descargar `base_image_url` | R2 público (4.1 paso 2) |
| `in call_diffusion` + `422` | FLUX rechazó el input | Reintentar; si persiste `DIFFUSION_PROMPT_STRENGTH=0.4` |
| `in mirror_url` / `botocore` / `SignatureDoesNotMatch` | Credenciales R2 mal | Regenerar token R2 (paso 9), verificar `S3_ENDPOINT_URL` con el Account ID correcto |
| `Falta foto de persona` | `DEFAULT_PERSON_IMAGE_URL` vacía | Paso 19 |
| Job desaparece (404) tras un rato | Supabase no activo y Railway reinició | `/health` → `"database": false` → revisar `SUPABASE_*` |

3. Tras corregir variables: Railway → Deployments → **Redeploy** → repetir sección 3.

### 4.3 SSE no responde (la tarjeta no avanza de etapa)

1. Abrir `https://<dominio-railway>/tryon/<id>` en el navegador → si el `stage` avanza ahí, el backend está bien y solo falla el stream; la web cae automáticamente a polling cada 2,5 s y terminará mostrando el resultado. No requiere acción.
2. Si en `/tryon/<id>` tampoco avanza → sección 4.2.
3. Si la web muestra el error `HTTP 404` o `Job no encontrado` → 4.2 última fila.
4. Si `/tryon/<id>/events` en el navegador del PC no muestra `data: {...}` al cabo de 3 s → Railway → Logs → buscar `Traceback` en el momento de la llamada → corregir y redeploy.

### 4.4 Backend health falla ("Backend no disponible" / `/health` no responde)

1. `https://<dominio-railway>/health` en el PC:
   - **No carga** → Railway → Deployments → estado. `Crashed` → Logs → primer `Error`/`Traceback` → normalmente variable mal escrita o `requirements` fallido → corregir → Redeploy. `Sleeping` → plan Hobby (1.1 punto 4).
   - **Carga con `missing_env` no vacío** → añadir esas variables (paso 19) → Redeploy.
2. `/health` carga en el PC pero la web dice "Backend no disponible":
   - Vercel → Settings → Environment Variables → `NEXT_PUBLIC_API_URL` exactamente igual al dominio Railway, con `https://`, sin barra final → Redeploy en Vercel.
   - Railway → `CORS_ORIGINS` exactamente igual a la URL de Vercel, con `https://`, sin barra final, sin espacios. Si usas varios dominios: separados por coma.
   - Consola del navegador (PC, F12) → error `CORS` confirma el punto anterior; error `net::ERR_NAME_NOT_RESOLVED` confirma el primero.
3. Railway → Settings → Networking → el dominio debe apuntar al puerto **8000**.

---

## 5. CRITERIO DE "SISTEMA FUNCIONANDO"

El sistema está listo para usuarios reales cuando se cumplen los 10 puntos, en el mismo día, sin intervención manual entre ellos:

1. `https://<dominio-railway>/health` → `{"status":"ok","missing_env":[],"storage":true,"database":true}`.
2. GitHub → Actions → últimos runs de `Backend` y `Frontend` lanzados por **push** (no manuales) en verde.
3. Railway → Deployments → último deploy **Active** creado por GitHub Actions (no por Auto Deploy).
4. Web abre en **dos móviles distintos** (iOS y Android, o dos redes distintas) con "Backend activo".
5. **Tres generaciones seguidas** desde móvil terminan en `done` con imagen visible, sin ningún `error`, tiempo total < 4 min cada una.
6. Cada resultado muestra las 3 etapas en orden en la UI y `job <id> done` en Railway Logs.
7. `final_image_url` y `base_image_url` de esas 3 generaciones empiezan por `S3_PUBLIC_BASE_URL` y abren tras 1 h (no caducan).
8. Supabase → `tryon_jobs` tiene 3 filas `done`; **Tus looks** en el móvil las muestra tras cerrar y reabrir el navegador.
9. `CORS_ORIGINS` en Railway ya no es `*` y la web sigue funcionando.
10. Replicate → Predictions y Anthropic → Usage muestran consumo coherente (2 predicciones + 1 llamada Claude por generación) y el coste por generación es ≈ 0,06–0,09 USD.

Cualquier punto en rojo → no está en producción. Volver a la sección 4 correspondiente.
