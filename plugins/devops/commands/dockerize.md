---
description: "Genera Dockerfile multi-stage, .dockerignore y compose.yaml de desarrollo para un servicio Node o Python (Next.js, NestJS, FastAPI, LangGraph) y los verifica construyendo la imagen localmente, sin publicar."
argument-hint: "<ruta-servicio>"
---

# /dockerize

Dockeriza el servicio indicado en: `$ARGUMENTS`

## 1. Validar el argumento
- Si `$ARGUMENTS` está vacío, pregunta al usuario la ruta del servicio (p. ej. `.`, `apps/web`, `services/api`) y detente hasta tenerla. Sugiere candidatos buscando directorios con `package.json` o `pyproject.toml`/`requirements.txt` que no estén en `node_modules`/`.venv`.
- Si la ruta no existe o no contiene un manifiesto reconocible, informa qué encontraste y pide confirmación o una ruta correcta.
- Trabaja siempre relativo a esa ruta (`SERVICE_DIR`). En monorepos, el contexto de build puede ser la raíz: decídelo en el paso 3.

## 2. Cargar contexto y skills
1. Carga la skill `core:project-context` y aplícala al repo y a `SERVICE_DIR`.
2. Lee `CLAUDE.md` (raíz y del servicio) si existen.
3. Carga la skill `devops:docker` y lee `references/dockerfiles.md` y `references/compose.md` de esa skill.

## 3. Detectar el stack del servicio
Determina y anota:
- **Tipo**: Next.js (`next` en dependencias), NestJS (`@nestjs/core`), FastAPI (`fastapi` en `pyproject.toml`/`requirements*.txt`), LangGraph/LangChain (`langgraph`, `langchain*`), otro Node/Python. Si es una app Expo (`expo` en dependencias, `app.json`/`eas.json`), explica que las apps móviles se construyen con EAS y no se dockerizan; ofrece dockerizar solo su backend o el export web y detente si el usuario no lo quiere.
- **Gestor y lockfile**: `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `uv.lock`, `requirements.txt`, `poetry.lock`. Sin lockfile, avisa: la instalación no será reproducible y recomienda generarlo.
- **Versión de runtime**: `.nvmrc`, `engines.node`, `packageManager`, `.python-version`, `requires-python`. Si no hay, usa Node 24 / Python 3.14 y dilo.
- **Monorepo**: `pnpm-workspace.yaml`, `turbo.json`, workspaces de uv. Si aplica, el contexto de build es la raíz y el Dockerfile usa `turbo prune` o copia los paquetes compartidos necesarios.
- **Arranque y puerto**: script `start`/`build`, `nest-cli.json`, módulo ASGI (`app.main:app`), puerto usado (`PORT`, `listen(...)`, `--port`).
- **Health**: busca rutas `/health`, `/ready`, `/api/health`. Si no existen, propón el cambio mínimo para añadirlas (no lo hagas sin avisar).
- **Dependencias externas**: Postgres, Redis, pgvector, colas (buscar `DATABASE_URL`, `REDIS_URL`, `prisma`, `typeorm`, `sqlalchemy`, `redis`, `bullmq`, `celery`, checkpointers de LangGraph).
- **Variables de entorno**: `.env.example`, `process.env.*`, `os.environ`, `BaseSettings`. Separa build-time (`NEXT_PUBLIC_*`) de runtime.
- **Archivos existentes**: si ya hay `Dockerfile`, `.dockerignore` o `compose*.yaml`, muéstrale al usuario un resumen de los problemas encontrados y propón modificarlos en lugar de sobrescribirlos; no los reemplaces sin confirmación.

## 4. Generar archivos
En `SERVICE_DIR` (o en la raíz si el contexto de build es la raíz):
1. **`Dockerfile`** a partir de la plantilla de la skill para el stack detectado:
   - `# syntax=docker/dockerfile:1`, `ARG` de versión, etapas nombradas y etapa final de producción al final.
   - Instalación con lockfile congelado y cache mounts.
   - Next.js: verifica `output: 'standalone'` en `next.config.*`; si falta, indícalo y propón añadirlo (cambio necesario para la plantilla).
   - Usuario no root con uid numérico, `EXPOSE`, `HEALTHCHECK` sin curl, `CMD` en forma exec.
   - Etapa `dev` (antes de la final) para compose.
2. **`.dockerignore`** basado en el de la skill, ajustado al stack (incluye siempre `.env*`, `.git`, `node_modules`, `.venv`).
3. **`compose.yaml`** de desarrollo: servicio de la app con `target: dev`, `develop.watch`, `env_file` opcional, y solo las dependencias detectadas (db, redis) con healthchecks, puertos en `127.0.0.1` y volúmenes con nombre.
4. **`.env.example`**: si no existe, créalo con las variables detectadas y valores placeholder. Nunca escribas valores reales ni copies un `.env` existente.
- No escribas secretos en ningún archivo. Credenciales de compose solo de desarrollo (`app/app`).

## 5. Verificar (sin publicar)
Ejecuta desde el directorio del contexto de build y reporta cada resultado:
1. `docker compose -f <compose> config -q` para validar compose.
2. `docker build --check -f <Dockerfile> .` (reglas de BuildKit).
3. `hadolint <Dockerfile>` si está instalado (o `docker run --rm -i hadolint/hadolint < Dockerfile` si Docker está disponible y el usuario lo acepta).
4. `docker build -t <servicio>:dockerize-test -f <Dockerfile> .` y reporta el tamaño con `docker image ls <servicio>:dockerize-test`.
5. Si el build pasa y el servicio puede arrancar sin dependencias externas, `docker run --rm -d -p <puerto>:<puerto> --name <servicio>-dockerize-test <imagen>`, espera unos segundos, consulta el health con `curl -fsS http://127.0.0.1:<puerto>/<health>` y luego `docker stop`. Si necesita db/redis, prueba con `docker compose up -d --build`, consulta el health y termina con `docker compose down` (sin `-v`).
6. Si `trivy` está instalado: `trivy image --severity HIGH,CRITICAL --ignore-unfixed <imagen>` y resume.
- Si Docker no está disponible o el daemon no corre, dilo y deja los comandos para que el usuario los ejecute.
- Si el build falla, corrige y reintenta (máximo 3 intentos) explicando cada cambio.
- **Nunca** ejecutes `docker push`, `docker buildx build --push`, `docker login` ni despliegues.

## 6. Resumen final
Entrega:
- Stack detectado y supuestos (versión de runtime, puerto, health).
- Archivos creados/modificados y cambios de código propuestos (standalone, health, shutdown hooks).
- Resultado de cada verificación (ok / falló / omitido y por qué) y tamaño de la imagen.
- Comandos para el usuario: `docker compose watch`, cómo construir la imagen de producción y el siguiente paso sugerido (`/devops:new-pipeline ci` para construirla en CI).
