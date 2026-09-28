---
name: docker
description: "Dockerfiles multi-stage, imágenes slim/distroless con usuario no root, caché de capas, .dockerignore, healthchecks, docker-compose de desarrollo y escaneo. Usar al dockerizar o revisar imágenes de Next.js, NestJS, FastAPI o apps LangChain/LangGraph."
---

# docker

## Objetivo
Producir imágenes pequeñas, reproducibles y seguras para los servicios del stack (Next.js, NestJS, FastAPI, LangChain/LangGraph) y un entorno local con `docker compose` que replique las dependencias (Postgres, Redis) sin instalar nada en la máquina.

## Cuándo aplicarla
- Crear o reescribir un `Dockerfile`, `.dockerignore` o `compose.yaml`.
- Revisar una imagen pesada, lenta de construir, que corre como root o sin healthcheck.
- Preparar la imagen que luego consumirán `devops:github-actions` (build/push) o `devops:kubernetes` (deploy).

Antes de empezar, carga `core:project-context` para detectar gestor de paquetes, versión del runtime y comando de arranque.

## Pasos
1. **Detectar el stack**: lockfile (`pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `uv.lock`, `requirements.txt`, `poetry.lock`), versión (`.nvmrc`, `engines.node`, `.python-version`, `requires-python`) y entrypoint (`next build`, `nest build` → `dist/main.js`, `app.main:app`).
2. **Elegir plantilla** de [references/dockerfiles.md](references/dockerfiles.md) y adaptarla: nombres de carpetas, puerto, ruta de health.
3. **Escribir `.dockerignore`** antes de construir (ver abajo). Sin él, `COPY . .` invalida la caché y puede filtrar `.env`.
4. **Configurar compose de desarrollo** con [references/compose.md](references/compose.md) si el servicio necesita db/redis.
5. **Verificar**: `docker build --check .`, `hadolint Dockerfile`, `docker build -t svc:dev .`, arrancar el contenedor y consultar el endpoint de health, escanear la imagen.
6. **No publicar**: `docker push` o `docker buildx build --push` solo con confirmación explícita del usuario.

## Convenciones

### Estructura del Dockerfile
- Primera línea `# syntax=docker/dockerfile:1` para tener BuildKit reciente (cache mounts, bind mounts, `--check`).
- Versión del runtime como `ARG` (`ARG NODE_VERSION=24`, `ARG PYTHON_VERSION=3.14`) y reutilizada en todas las etapas.
- Etapas con nombre: `base` → `deps` → `build` → `runtime` (o `runner`). La etapa final es la última del archivo para que `docker build` sin `--target` produzca la de producción. Si hace falta una etapa `dev` para compose, ubícala antes de `runtime` y selecciónala con `target: dev`.
- Orden por frecuencia de cambio: manifiestos y lockfile → instalación de dependencias → código fuente → build.
- Usa `RUN --mount=type=cache,...` para cachés de pnpm/npm/uv/pip en lugar de dejar la caché dentro de la capa.
- `CMD`/`ENTRYPOINT` en forma exec (JSON) para que el proceso reciba `SIGTERM` directamente (apagado limpio en Kubernetes).

### Imágenes base (verifica etiquetas vigentes antes de fijarlas)
| Runtime | Build | Runtime recomendado | Alternativa mínima |
|---|---|---|---|
| Node | `node:24-slim` (LTS actual) | `node:24-slim` | `gcr.io/distroless/nodejs24-debian13:nonroot` |
| Python | `python:3.14-slim` | `python:3.14-slim` | `gcr.io/distroless/python3-debian13:nonroot` (trae el Python de Debian 13, 3.13: construye con `python:3.13-slim-trixie` para que el venv sea compatible) |

- Evita `alpine` para Python (musl rompe wheels y alarga builds) y para Node con dependencias nativas (sharp, bcrypt, prisma engines) salvo que esté probado.
- Nunca `:latest`. En producción fija por digest (`node:24-slim@sha256:...`) y deja que Dependabot/Renovate lo actualice.
- Node 25+ ya no incluye Corepack; en Node 24 basta `corepack enable`. Con versiones posteriores instala pnpm con `npm i -g pnpm@<versión>` o fija `packageManager` y usa `npx corepack`.
- Distroless no tiene shell ni curl: los healthchecks deben usar el propio runtime (`node -e`, `python -c`) y para depurar existe la variante `:debug-nonroot`.

### Usuario no root
- Node: las imágenes oficiales traen el usuario `node` (uid 1000): `USER node`.
- Python slim: crea un usuario de sistema con uid fijo (`useradd --system --uid 10001 ...`) para poder declarar `runAsUser: 10001` en Kubernetes.
- Distroless: usa la etiqueta `:nonroot` (uid 65532).
- Los archivos de la aplicación pueden quedar propiedad de root (solo lectura para el proceso); da `--chown` únicamente a los directorios que la app escribe (p. ej. `.next/cache`).

### Variables, argumentos y secretos
- `ENV` solo para configuración no sensible y defaults (`NODE_ENV=production`, `PORT`, `PYTHONUNBUFFERED=1`).
- Secretos de build (token de npm privado, índice de PyPI privado) con `RUN --mount=type=secret,id=npmrc,target=/root/.npmrc ...` y `docker build --secret id=npmrc,src=$HOME/.npmrc`. Nunca `ARG`/`ENV` con secretos: quedan en el historial de la imagen.
- Secretos de runtime (DB URL, API keys de LLM) se inyectan al ejecutar (compose `env_file`, Kubernetes Secret), no en la imagen.
- Next.js: las `NEXT_PUBLIC_*` se incrustan en el bundle durante `next build`, así que son `ARG` de build y públicas por definición. Todo lo demás se lee en runtime.

### Caché de capas
- Copia primero `package.json` + lockfile (o `pyproject.toml` + `uv.lock`) y resuelve dependencias; el `COPY . .` va después.
- Instalación siempre congelada: `pnpm install --frozen-lockfile`, `npm ci`, `uv sync --locked`, `pip install -r requirements.txt` con hashes si es posible.
- En CI usa caché de BuildKit remota (`cache-from/cache-to type=gha` o `type=registry`), ver `devops:github-actions`.

### .dockerignore base
```gitignore
.git
.github
**/node_modules
**/.next
dist
coverage
.turbo
**/__pycache__
**/*.pyc
.venv
.pytest_cache
.mypy_cache
.ruff_cache
.env
.env.*
!.env.example
*.pem
*.key
Dockerfile*
compose*.yaml
docker-compose*.yml
README.md
docs
```
Ajusta: si el build necesita un archivo ignorado (p. ej. `README.md` para `uv build`), quítalo de la lista.

### Healthchecks
- Expón un endpoint barato (`/health` o `/api/health`) que no dependa de servicios externos para liveness; un `/ready` que sí verifique db/redis para readiness.
- `HEALTHCHECK` en el Dockerfile sirve a `docker run` y compose; Kubernetes lo ignora y usa sus propias probes (`devops:kubernetes`).
- Ejemplo Node sin curl: `HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 CMD ["node", "-e", "fetch('http://127.0.0.1:3000/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]`

### Particularidades por stack
- **Next.js**: `output: 'standalone'` en `next.config.*`; la imagen final copia `.next/standalone`, `.next/static` y `public`, y arranca con `node server.js` y `HOSTNAME=0.0.0.0`.
- **NestJS**: `nest build` y luego `pnpm prune --prod` (o `npm prune --omit=dev`); arranca con `node dist/main.js`. Llama a `app.enableShutdownHooks()` para cerrar conexiones al recibir `SIGTERM`.
- **FastAPI**: un proceso uvicorn por contenedor (`uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers`) y escala con réplicas; `--workers` solo en VMs sin orquestador.
- **LangChain/LangGraph**: igual que FastAPI. Para streaming (SSE) sube los timeouts del proxy/ingress y evita buffering. Si se usa LangGraph Server, el `langgraph-cli` (`langgraph dockerfile` / `langgraph build`) genera la imagen; verifica la versión del CLI antes de documentarlo.
- **Expo**: las apps móviles no se dockerizan; se construyen con EAS (ver `devops:github-actions`). Solo se dockeriza el backend o el export web si aplica.

## Escaneo y verificación
```bash
docker build --check .                          # reglas de build de BuildKit, sin construir
hadolint Dockerfile                             # o: docker run --rm -i hadolint/hadolint < Dockerfile
docker build -t svc:dev .
docker run --rm -p 3000:3000 --env-file .env svc:dev
docker image ls svc:dev                         # revisa tamaño
trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 svc:dev
docker scout cves svc:dev                       # alternativa si Docker Scout está disponible
```
- Genera SBOM y provenance al publicar desde CI (`sbom: true`, `provenance: mode=max` en `docker/build-push-action`).
- Fija las herramientas de escaneo por versión/SHA: en marzo de 2026 las etiquetas de `aquasecurity/trivy-action` fueron reescritas con malware (incidente TeamPCP); usa versiones posteriores a la remediación y verifica los advisories.

## Antipatrones
- `FROM node:latest` o imagen completa (`node:24`, `python:3.14`) en runtime: +700 MB y más CVEs.
- `COPY . .` antes de instalar dependencias o sin `.dockerignore`.
- `RUN npm install` (no determinista) en vez de `npm ci`/`--frozen-lockfile`.
- `apt-get install` sin `--no-install-recommends` y sin limpiar `/var/lib/apt/lists/*`; herramientas de build (gcc, git) en la imagen final.
- Correr como root, `chmod -R 777`, o `sudo` dentro del contenedor.
- `CMD npm start` (forma shell + npm como PID 1: no propaga señales). Usa `node` directamente.
- Secretos en `ARG`, `ENV` o copiados como archivo; `.env` dentro de la imagen.
- Healthcheck con `curl` sobre una imagen que no lo tiene.
- Una sola imagen para dev y prod con `nodemon`/`--reload` en el `CMD` final.

## Checklist final
- [ ] Multi-stage; la etapa final solo contiene runtime + artefactos.
- [ ] Imagen base slim/distroless con versión explícita (digest en prod).
- [ ] `.dockerignore` excluye `.git`, `node_modules`, `.venv`, `.env*`, llaves.
- [ ] Instalación con lockfile congelado y cache mounts.
- [ ] `USER` no root con uid numérico conocido.
- [ ] `CMD` en forma exec; la app maneja `SIGTERM`.
- [ ] `EXPOSE` y puerto configurables por `PORT`; bind a `0.0.0.0`.
- [ ] Healthcheck sin dependencias ausentes en la imagen.
- [ ] Sin secretos en capas (`docker history --no-trunc` limpio).
- [ ] `hadolint` y `docker build --check` sin errores; escaneo sin CRITICAL corregibles.

## Recursos
- [references/dockerfiles.md](references/dockerfiles.md): plantillas completas para Next.js standalone, NestJS, FastAPI con uv y con pip, y variantes distroless. Léelo al escribir un Dockerfile nuevo.
- [references/compose.md](references/compose.md): `compose.yaml` de desarrollo con Postgres, Redis, healthchecks y `docker compose watch`. Léelo al montar el entorno local.
- Skills relacionadas: `devops:github-actions` (build/push en CI), `devops:kubernetes` (probes y securityContext coherentes con la imagen), `core:project-context`.
