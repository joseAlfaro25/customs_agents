# Señales de stack (referencia detallada)

Úsala cuando `detect_stack.py` no sea concluyente o en monorepos.

## Gestor de paquetes

| Archivo | Gestor | Instalar | Ejecutar script |
|---|---|---|---|
| `pnpm-lock.yaml` | pnpm | `pnpm install` | `pnpm <script>` |
| `package-lock.json` | npm | `npm ci` | `npm run <script>` |
| `yarn.lock` | yarn | `yarn install` | `yarn <script>` |
| `bun.lock` / `bun.lockb` | bun | `bun install` | `bun run <script>` |
| `uv.lock` | uv | `uv sync` | `uv run <cmd>` |
| `poetry.lock` | poetry | `poetry install` | `poetry run <cmd>` |
| `requirements*.txt` sin lock | pip | `pip install -r requirements.txt` | `python -m <cmd>` |

`packageManager` en `package.json` tiene prioridad sobre el lockfile.

## Monorepos

| Señal | Herramienta |
|---|---|
| `pnpm-workspace.yaml` | pnpm workspaces |
| `workspaces` en `package.json` | npm/yarn/bun workspaces |
| `turbo.json` | Turborepo (`turbo run <task> --filter=<pkg>`) |
| `nx.json` | Nx (`nx run <proj>:<target>`) |
| `[tool.uv.workspace]` en `pyproject.toml` | uv workspace |

Carpetas típicas: `apps/web` (Next.js), `apps/api` (NestJS/FastAPI), `apps/mobile` (Expo), `packages/*` (librerías compartidas), `infra/` (Terraform), `deploy/` o `k8s/` (manifiestos).

En un monorepo, trabaja siempre **dentro del paquete afectado** y ejecuta la verificación filtrada a ese paquete.

## Frontend

| Señal | Significado |
|---|---|
| `app/` con `layout.tsx` | Next.js App Router |
| `pages/` con `_app.tsx` | Next.js Pages Router (legacy; no mezclar sin plan) |
| `vite.config.*` + `react` | React SPA con Vite |
| `tailwind.config.*` o `@import "tailwindcss"` en CSS | Tailwind (v4 usa config en CSS) |
| `components.json` | shadcn/ui |
| `@tanstack/react-query`, `zustand`, `redux` | Librería de estado/datos |
| `zod`, `valibot` | Validación en runtime |

## Backend Node

| Señal | Significado |
|---|---|
| `nest-cli.json`, `@nestjs/core` | NestJS |
| `@nestjs/typeorm`, `typeorm` | TypeORM |
| `prisma/schema.prisma` | Prisma |
| `@nestjs/swagger` | OpenAPI generado |

## Backend Python

| Señal | Significado |
|---|---|
| `fastapi` | FastAPI |
| `pydantic>=2` | Pydantic v2 (`model_dump`, `field_validator`) |
| `sqlalchemy>=2`, `alembic.ini` | SQLAlchemy 2 + migraciones |
| `pytest`, `pytest-asyncio`, `httpx` | Tests |
| `ruff`, `mypy`, `pyright` | Calidad |

## IA / LLM

| Señal | Significado |
|---|---|
| `langchain`, `langchain-core`, `langchain-<provider>` | LangChain (ver versión mayor: 1.x cambió APIs de agentes) |
| `langgraph`, `langgraph.json` | LangGraph (y LangGraph Platform si hay `langgraph.json`) |
| `langsmith`, `LANGSMITH_API_KEY` en `.env.example` | LangSmith tracing/evals |
| `pgvector`, `chromadb`, `qdrant-client`, `pinecone` | Vector store |

## Mobile

| Señal | Significado |
|---|---|
| `expo` en dependencies | Expo (leer versión = SDK) |
| `app/_layout.tsx` + `expo-router` | Expo Router |
| `ios/` y `android/` versionados | Proyecto con carpetas nativas (prebuild ya ejecutado o bare) |
| `eas.json` | EAS Build/Submit/Update |

## DevOps

| Señal | Significado |
|---|---|
| `Dockerfile*`, `.dockerignore` | Contenedores |
| `compose.yaml`, `docker-compose*.yml` | Entorno local multi-servicio |
| `.github/workflows/*.yml` | GitHub Actions |
| `Chart.yaml` | Helm chart |
| `kustomization.yaml` | Kustomize |
| `*.tf`, `.terraform.lock.hcl` | Terraform |
| `provider "aws"`, `@aws-sdk/*`, `boto3`, `aws-cdk`, `cdk.json`, `samconfig.toml`, `aws-actions/*`, `.aws/` | AWS |
| `provider "google"`, `@google-cloud/*`, `google-cloud-*`, `cloudbuild.yaml`, `app.yaml`, `google-github-actions/*` | Google Cloud |
