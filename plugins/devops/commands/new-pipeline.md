---
description: "Genera un workflow de GitHub Actions de CI (lint, test, build) o CD (imagen por digest, deploy por environments con OIDC) adaptado al stack del repo, con permisos mínimos y actions pinneadas por SHA; lo valida con actionlint sin ejecutarlo."
argument-hint: "<ci|cd> [ruta-servicio]"
---

# /new-pipeline

Crea un workflow de GitHub Actions. Argumentos recibidos: `$ARGUMENTS`

## 1. Validar argumentos
- Primer argumento = tipo: `ci` o `cd` (insensible a mayúsculas). Segundo argumento opcional = ruta del servicio (por defecto `.`).
- Si `$ARGUMENTS` está vacío o el tipo no es `ci` ni `cd`, pregunta: "¿Qué pipeline quieres: `ci` (lint, test, build en cada PR) o `cd` (build de imagen y despliegue por entornos)?" y detente hasta tener respuesta.
- Si la ruta no existe, pide una válida.

## 2. Cargar contexto y skills
1. Carga `core:project-context` y aplícala al repo y a la ruta del servicio.
2. Lee `CLAUDE.md` si existe.
3. Carga `devops:github-actions` y lee `references/ci.md` (tipo `ci`) o `references/cd.md` (tipo `cd`) de esa skill.
4. Carga `core:git-workflow` para alinear ramas y tags con los triggers.
5. Para `cd`, carga también `devops:docker` y, si hay manifiestos de Kubernetes o Helm, `devops:kubernetes`.
6. Si el pipeline despliega a AWS o Google Cloud (o autentica contra ellos), carga `devops:cloud-project-standard` (**obligatoria**) y su referencia del proveedor: OIDC / Workload Identity Federation restringido al repo y al environment, roles separados para `plan` y `apply`, imagen por digest y aprobación para producción.

## 3. Detectar el stack y el estado actual
- Workflows existentes en `.github/workflows/`: si ya hay un CI/CD equivalente, resume qué hace y qué le falta y propón modificarlo en lugar de crear uno paralelo. No sobrescribas sin confirmación.
- Servicio: Node (Next.js, NestJS) o Python (FastAPI, LangChain/LangGraph) o Expo; monorepo o no (`pnpm-workspace.yaml`, `turbo.json`, varias apps).
- Gestor y versión: `packageManager`, lockfile, `.nvmrc`/`engines`, `uv.lock`/`requirements*.txt`, `.python-version`.
- Comandos reales: scripts de `package.json` (`lint`, `typecheck`, `test`, `build`), herramientas Python en `pyproject.toml` (ruff, mypy/pyright, pytest). Usa solo comandos que existen; si falta alguno importante, dilo y propón añadirlo, pero no lo inventes en el workflow.
- Servicios que necesitan los tests (Postgres, Redis) para declararlos como `services:`.
- Para `cd`: `Dockerfile` (si no existe, sugiere ejecutar antes `/devops:dockerize <ruta>`), registro destino (GHCR por defecto; ECR/Artifact Registry/ACR si hay indicios en `infra/`), proveedor cloud y plataforma de despliegue (`deploy/` con Kustomize, `charts/` con Helm, GitOps, Cloud Run/ECS, EAS para Expo).
- Pregunta solo lo que cambia el resultado y no puedas deducir (p. ej. proveedor cloud o nombres de environments). Para el resto usa defaults y decláralos.

## 4. Generar el workflow
Comunes a ambos tipos:
- `permissions: contents: read` a nivel de workflow; permisos extra solo en el job que los necesite.
- Todas las actions externas pinneadas por SHA de 40 caracteres con comentario de versión, usando la tabla de la skill. Luego ejecuta `python3 "<carpeta de la skill github-actions>/scripts/pin-actions.py" .github/workflows` (dry-run) para detectar referencias sin pinnear o SHAs a verificar; si `gh` no está disponible o autenticado, indícalo.
- `concurrency`, `timeout-minutes` en cada job, `actions/checkout` con `persist-credentials: false`.
- Ningún `${{ }}` con datos controlados por usuarios dentro de `run:`; pásalos por `env:`.
- Ningún secreto en el archivo: solo referencias `secrets.*`/`vars.*`.

**Tipo `ci`** → `.github/workflows/ci.yml`:
- Triggers: `pull_request`, `push` a la rama por defecto, `workflow_dispatch`.
- Jobs: `lint` (lint + typecheck/format), `test` (con `services:` si hacen falta; matriz solo si el proyecto soporta varias versiones), `build` (build de la app y `docker/build-push-action` con `push: false` si hay Dockerfile).
- Caché: pnpm vía `pnpm/action-setup` + `actions/setup-node` con `cache: pnpm`; npm con `cache: npm`; uv con `astral-sh/setup-uv` `enable-cache: true`; BuildKit con `type=gha`.
- Monorepo: filtro por rutas y un job agregador `ci-ok` como check requerido.
- Expo: `lint`, `typecheck`, `test` y opcionalmente `npx expo-doctor`; sin builds nativos en CI de PR.

**Tipo `cd`** → `.github/workflows/cd.yml` + reusables `_build-image.yml` y `_deploy.yml` si no existen:
- Triggers: `push` a la rama por defecto (staging) y tags `v*` (production), `workflow_dispatch`.
- Build una vez: metadata-action, build-push con `provenance: mode=max`, `sbom: true`, caché gha y `actions/attest-build-provenance`; salida `digest`.
- Deploy por `environment` (`staging`, luego `production`), con `concurrency` por entorno sin cancelación, desplegando el mismo digest.
- Autenticación cloud por OIDC (`id-token: write`) con la action oficial del proveedor; nunca llaves estáticas.
- Despliegue según la plataforma detectada: Kustomize (`kustomize edit set image` + `kubectl apply -k` + `rollout status`), Helm (`helm upgrade --install --atomic --wait`), GitOps (commit del digest al repo de manifiestos) o EAS (`expo/expo-github-action` + `eas build`/`eas update`, `EXPO_TOKEN` en el environment).
- Si no se detecta plataforma, genera solo build + push + un job de deploy con un paso placeholder claramente marcado y explícalo.

## 5. Verificar (sin ejecutar el pipeline)
1. Valida sintaxis YAML con `python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" <archivos>`.
2. `actionlint <archivos>` si está instalado (o `docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest -color` si Docker está disponible). Corrige lo que reporte.
3. `zizmor <archivos>` si está instalado (o `uvx zizmor` si `uv` existe). Corrige hallazgos de severidad media o superior o justifica por qué no aplican.
4. Revisa manualmente la checklist final de la skill `devops:github-actions`.
- **Nunca** ejecutes `gh workflow run`, `git push`, `gh secret set`, `gh variable set` ni crees environments sin confirmación explícita del usuario.

## 6. Resumen final
Entrega:
- Tipo de pipeline, stack detectado y supuestos.
- Archivos creados/modificados con el propósito de cada job.
- Resultado de validaciones (YAML, actionlint, zizmor, pinning): ok / falló / omitido.
- Configuración pendiente en GitHub y en la nube, con nombres exactos: environments y reviewers, `vars.*` (región, rol, cluster, URL), `secrets.*` (solo los inevitables, p. ej. `EXPO_TOKEN`), rol OIDC con su `sub` esperado (`repo:<org>/<repo>:environment:<env>`), branch protection con los checks requeridos. Sugiere `devops:iac-developer` para crear el rol OIDC con Terraform.
- Cómo probarlo: abrir un PR (ci) o hacer push a la rama por defecto / crear un tag (cd), acciones que ejecuta el usuario.
