# Plantillas de Dockerfile por stack

Plantillas base verificadas a septiembre de 2026. Antes de usarlas:
- Confirma la versión del runtime del proyecto (`.nvmrc`, `engines`, `.python-version`) y ajusta `ARG`.
- Verifica que las etiquetas existan (`docker pull node:24-slim`) y en producción fíjalas por digest.
- Ajusta puertos, rutas de health y nombres de carpetas (`app/`, `src/`).

Índice:
1. Next.js (App Router, `output: 'standalone'`, pnpm)
2. NestJS (pnpm o npm)
3. FastAPI / LangGraph con uv
4. FastAPI con pip + requirements.txt
5. Variantes distroless
6. Etapa `dev` para compose

---

## 1. Next.js standalone (pnpm)

Requisito en `next.config.ts`:
```ts
const nextConfig = { output: 'standalone' };
export default nextConfig;
```

```dockerfile
# syntax=docker/dockerfile:1
ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-slim AS base
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile

FROM base AS build
ENV NEXT_TELEMETRY_DISABLED=1
# Variables públicas: se incrustan en el bundle. Nunca pases secretos aquí.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:${NODE_VERSION}-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=build /app/public ./public
# .next debe ser escribible por el usuario (cache de ISR / image optimization)
RUN mkdir .next && chown node:node .next
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["node", "server.js"]
```

Notas:
- Con npm: `COPY package.json package-lock.json ./` y `RUN --mount=type=cache,target=/root/.npm npm ci`; quita `corepack`.
- Monorepo (Turborepo): usa `turbo prune <app> --docker` en una etapa previa y copia `out/json` antes de instalar y `out/full` antes de construir. La salida standalone queda en `apps/<app>/.next/standalone` e incluye la ruta relativa: el `CMD` pasa a `node apps/<app>/server.js`.
- Si no existe `public/`, elimina esa línea `COPY` o crea la carpeta vacía.
- Crea el route handler `app/api/health/route.ts` que responda 200 sin tocar dependencias externas.

---

## 2. NestJS

```dockerfile
# syntax=docker/dockerfile:1
ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-slim AS base
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build \
 && pnpm prune --prod

FROM node:${NODE_VERSION}-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["node", "dist/main.js"]
```

Notas:
- Con npm: `npm ci` en `deps` y `npm run build && npm prune --omit=dev` en `build`.
- Prisma: ejecuta `prisma generate` en `build` y copia también `prisma/` si las migraciones se lanzan desde el contenedor (preferible un Job separado, ver `devops:kubernetes`).
- En `main.ts`: `app.enableShutdownHooks()` y `await app.listen(process.env.PORT ?? 3000, '0.0.0.0')`.
- Health: `@nestjs/terminus` para `/health` (liveness) y `/ready` (indicadores de db/redis).

---

## 3. FastAPI / LangGraph con uv

Supone `pyproject.toml` + `uv.lock` y el código en `app/` (módulo `app.main:app`).

```dockerfile
# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.14

FROM python:${PYTHON_VERSION}-slim AS build
# Fija la versión de uv (verifica la última en https://github.com/astral-sh/uv/releases)
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# 1) Solo dependencias: capa cacheable mientras no cambie el lockfile
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project
# 2) Código + instalación del proyecto
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
# El venv y el código viven en la misma ruta que en build (/app), así los paths del venv siguen siendo válidos
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/app /app/app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=3).status == 200 else 1)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

Notas:
- Si el proyecto está empaquetado (tiene `[build-system]`), puedes usar `--no-editable` en ambos `uv sync` y copiar solo `/app/.venv`.
- Dependencias con extensiones C sin wheel (p. ej. `psycopg` sin binario): instala `build-essential` solo en la etapa `build` con `apt-get install -y --no-install-recommends` y `rm -rf /var/lib/apt/lists/*`. En runtime agrega únicamente las libs compartidas (`libpq5`).
- `--forwarded-allow-ips "*"` es aceptable solo detrás de un proxy/ingress de confianza; si no, limítalo a su IP/CIDR.
- LangGraph / LangChain: las API keys de LLM (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGSMITH_API_KEY`) llegan por variables de entorno en runtime. Para SSE/streaming, no uses `--workers` y ajusta `--timeout-keep-alive` si el proxy mantiene conexiones largas.
- `uv sync` sin `UV_NO_DEV=1` instala el grupo `dev`; en la etapa de tests de CI sí lo quieres.

---

## 4. FastAPI con pip + requirements.txt

```dockerfile
# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.14

FROM python:${PYTHON_VERSION}-slim AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY app/ ./app/
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

Recomienda migrar a un lockfile real (`uv pip compile --generate-hashes` o `uv.lock`) y usar `pip install --require-hashes`.

---

## 5. Variantes distroless

Sustituye solo la etapa final.

Node (NestJS):
```dockerfile
FROM gcr.io/distroless/nodejs24-debian13:nonroot AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=3000
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
EXPOSE 3000
# El ENTRYPOINT ya es node: el CMD es solo el script
CMD ["dist/main.js"]
```

Next.js: igual que la plantilla 1, pero sin el `RUN mkdir` (no hay shell): copia `standalone` y `static` con `--chown=65532:65532` (el `.next` de standalone queda escribible) y usa `CMD ["server.js"]`.

Python: `gcr.io/distroless/python3-debian13:nonroot` trae el Python del sistema de Debian 13 (3.13) en `/usr/bin/python3`. Un venv creado en `python:3.13-slim-trixie` apunta a `/usr/local/bin/python3`, que no existe en distroless, así que el venv no funciona tal cual. La alternativa habitual es copiar solo `site-packages` y fijar `PYTHONPATH`:
```dockerfile
FROM gcr.io/distroless/python3-debian13:nonroot AS runtime
WORKDIR /app
COPY --from=build /app/.venv/lib/python3.13/site-packages /app/site-packages
COPY --from=build /app/app /app/app
ENV PYTHONPATH=/app/site-packages PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Pruébalo bien (extensiones C que dependan de libs ausentes fallan en runtime). Si resulta frágil, quédate con `python:*-slim` + usuario no root, que es la opción recomendada por defecto.

Depuración: `:debug-nonroot` incluye busybox (`docker run --rm -it --entrypoint=sh img:debug`). No la uses en producción.

---

## 6. Etapa `dev` para compose

Añade antes de `runtime` para que `docker build` sin `--target` siga produciendo la imagen de producción.

Node:
```dockerfile
FROM base AS dev
COPY --from=deps /app/node_modules ./node_modules
COPY . .
USER node
CMD ["pnpm", "dev"]
```

Python (uv):
```dockerfile
FROM build AS dev
ENV UV_NO_DEV=0
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```
