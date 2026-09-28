---
name: github-actions
description: "Workflows de GitHub Actions: CI de lint/test/build con caché pnpm/uv, matrices, build y push de imágenes, deploy por environments con aprobaciones, OIDC hacia AWS/GCP/Azure, permisos mínimos, pinning por SHA, reusable workflows y concurrency. Usar al crear, revisar o depurar workflows."
---

# github-actions

## Objetivo
Pipelines rápidos, reproducibles y seguros por defecto: CI en cada PR, CD controlado por entornos con aprobación, sin llaves de larga duración y con la cadena de suministro (actions, imágenes) fijada.

## Cuándo aplicarla
- Crear `ci.yml`/`cd.yml` para un servicio nuevo o migrar desde otro CI.
- Añadir build/push de imágenes, despliegues por entorno o `terraform plan` en PR.
- Revisar un workflow lento, inseguro (`pull_request_target`, `permissions: write-all`, llaves AWS en secrets) o que falla de forma intermitente.

Carga antes `core:project-context` (gestor de paquetes, scripts `lint`/`test`/`build`, monorepo o no) y `core:git-workflow` (ramas, tags de release).

## Estructura
```
.github/
├── workflows/
│   ├── ci.yml                 # PR + push a main: lint, typecheck, test, build
│   ├── cd.yml                 # push a main / tags: build imagen + deploy staging → production
│   ├── _build-image.yml       # reusable (on: workflow_call), prefijo _ = no se dispara solo
│   └── _deploy.yml            # reusable
├── actions/
│   └── setup-node-pnpm/action.yml   # composite action para pasos repetidos
└── dependabot.yml             # incluye package-ecosystem: github-actions
```
Un workflow por propósito; nombres de jobs cortos y estables (se usan en branch protection como required checks).

## Pasos
1. Detectar stack y comandos reales (`package.json` scripts, `pyproject.toml` con ruff/pytest/mypy). No inventes scripts que no existen: si falta `lint` o `typecheck`, propón añadirlos.
2. Partir de las plantillas de [references/ci.md](references/ci.md) o [references/cd.md](references/cd.md).
3. Aplicar las convenciones de seguridad de abajo (permisos, pinning, OIDC, sin inyección).
4. Resolver SHAs de las actions con `scripts/pin-actions.py` (ver Recursos).
5. Validar con `actionlint` y, si está disponible, `zizmor` (auditoría de seguridad de workflows).
6. No disparar workflows de deploy ni crear environments/secrets en el repo sin confirmación explícita del usuario.

## Convenciones

### Triggers
- CI: `pull_request` (sin filtro de tipos) + `push` a `main`. Añade `workflow_dispatch` para re-ejecución manual.
- Monorepo: `paths:` en el trigger o `dorny/paths-filter` por job; cuidado, un check requerido que no se ejecuta por `paths` bloquea el merge: usa un job agregador que siempre corra.
- CD: `push` a `main` (staging) y `push: tags: ['v*']` o `release: published` (production).
- `schedule` con cron en UTC y solo en la rama por defecto.
- **Nunca** `pull_request_target` para construir o testear código del PR: corre con secretos y token de escritura. Si es imprescindible (etiquetar PRs de forks), no hagas checkout del head del PR (`actions/checkout` v7 ya lo bloquea por defecto en `pull_request_target` y `workflow_run`).

### Permisos mínimos
- A nivel de workflow `permissions: contents: read` y amplía solo en el job que lo necesite:
  - `packages: write` para GHCR; `id-token: write` para OIDC; `attestations: write` para attestations; `pull-requests: write` para comentar planes.
- `actions/checkout` con `persist-credentials: false` salvo que el job haga `git push`.

### Pinning de actions
- Fija por SHA completo de 40 caracteres con la versión en comentario: `uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`.
- Las etiquetas son mutables: en marzo de 2026 se reescribieron 76 de 77 tags de `aquasecurity/trivy-action` para robar credenciales. Solo el SHA protege.
- Dependabot (`package-ecosystem: github-actions`) actualiza SHA y comentario. Actions locales (`./.github/actions/...`) y reusable workflows del mismo repo no se pinnean.
- Imágenes en `container:`/`services:` también con etiqueta explícita (idealmente digest).

Versiones estables verificadas el 2026-09-28 (vuelve a verificar con `gh api repos/<owner>/<repo>/releases/latest`):

| Action | Versión | SHA |
|---|---|---|
| actions/checkout | v7.0.1 | 3d3c42e5aac5ba805825da76410c181273ba90b1 |
| actions/setup-node | v7.0.0 | 820762786026740c76f36085b0efc47a31fe5020 |
| actions/setup-python | v7.0.0 | 5fda3b95a4ea91299a34e894583c3862153e4b97 |
| actions/cache | v6.1.0 | 55cc8345863c7cc4c66a329aec7e433d2d1c52a9 |
| pnpm/action-setup | v6.1.0 | ea17c68df8912ef543352723c149a84f56e3d413 |
| astral-sh/setup-uv | v10.2.0 | c18668ad3cf93ea998bef934396af7bb5c839dc7 |
| docker/setup-buildx-action | v4.4.1 | f87e5991a6d7451dcb8d9637bfbc97413f497069 |
| docker/login-action | v4.6.0 | dbcb813823bdd20940b903addbd779551569679f |
| docker/metadata-action | v6.2.0 | dc802804100637a589fabce1cb79ff13a1411302 |
| docker/build-push-action | v7.4.0 | c3c9e263c25d99ce0380d002d59b67737d91b0dc |
| actions/attest-build-provenance | v4.2.2 | 4d101475d8b20a2381f78447822ac1eab6504dd8 |
| aws-actions/configure-aws-credentials | v6.3.0 | e1253824e5c10ff9df46874f81ed3ec929e19cfd |
| aws-actions/amazon-ecr-login | v2.1.7 | 03f1aad4c6c7ffd436567f42f9384779290529bd |
| google-github-actions/auth | v3.0.0 | 7c6bc770dae815cd3e89ee6cdf493a5fab2cc093 |
| azure/login | v3.1.0 | a641126d1b8aa4d1fa005f4f92df94a3a4c4c906 |
| hashicorp/setup-terraform | v4.0.1 | dfe3c3f87815947d99a8997f908cb6525fc44e9e |
| terraform-linters/setup-tflint | v6.3.1 | 1cf010d3c7aef302051ccdb68c14c5dc2efa34ef |
| expo/expo-github-action | 9.0.0 | eab7a230208c952974db8c3245cfd78402c7b385 |

Las actions con runtime `node24` requieren runner v2.327.1 o superior (relevante en self-hosted/GHES).

### Caché
- Node + pnpm: `pnpm/action-setup` (lee `packageManager` de `package.json`) antes de `actions/setup-node` con `cache: pnpm`. Desde setup-node v6 la caché automática solo aplica a npm; para pnpm/yarn declárala explícitamente.
- Python + uv: `astral-sh/setup-uv` con `enable-cache: true` (v10 la desactiva por defecto en `pull_request_target`, `workflow_run` y `release` para evitar cache poisoning).
- pip puro: `actions/setup-python` con `cache: pip` y `cache-dependency-path`.
- Docker: `cache-from: type=gha` / `cache-to: type=gha,mode=max` en `docker/build-push-action`.
- No caches `node_modules` directamente; cachea el store del gestor.
- Jobs que publican o despliegan no deberían restaurar cachés escritas por PRs no confiables.

### Concurrency y tiempos
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```
- En deploys usa un grupo por entorno (`deploy-production`) con `cancel-in-progress: false` para no cortar un despliegue a medias.
- `timeout-minutes` en cada job (el default es 360).

### Matrices
- `strategy.matrix` para versiones soportadas (`node: [22, 24]`, `python: ['3.13', '3.14']`) o sistemas; `fail-fast: false` en CI para ver todos los fallos.
- `include`/`exclude` para combinaciones puntuales; no multipliques la matriz en jobs de build/deploy.

### Entornos y aprobaciones
- Un `environment` por destino (`staging`, `production`) con: required reviewers, deployment branches/tags restringidos (`main`, `v*`), wait timer opcional y secrets/variables propios.
- El job de deploy declara `environment: { name: production, url: ... }`; la aprobación la gestiona GitHub, no el workflow.
- Variables no sensibles en `vars.*` (región, cluster, cuenta); secretos en `secrets.*` del environment, nunca a nivel de repo si solo los usa un entorno.

### OIDC en vez de llaves
- `permissions: id-token: write` en el job y la action oficial del proveedor: `aws-actions/configure-aws-credentials` (`role-to-assume`), `google-github-actions/auth` (`workload_identity_provider` + `service_account`) o `azure/login` (`client-id`, `tenant-id`, `subscription-id`).
- La relación de confianza del lado cloud debe restringir el `sub`: `repo:<org>/<repo>:environment:production` o `repo:<org>/<repo>:ref:refs/heads/main`. Nunca `repo:<org>/*`.
- Un rol por entorno con permisos mínimos (push a ECR/Artifact Registry + deploy), no `AdministratorAccess`.
- Nada de `AWS_ACCESS_KEY_ID`/JSON de service account en secrets.

### Inyección en scripts
- Nunca interpoles contexto controlado por usuarios dentro de `run:`: `${{ github.event.pull_request.title }}`, `...head_ref`, `...issue.body`, `...comment.body`, nombres de ramas.
- Pásalo por variable de entorno y cítala:
```yaml
- name: Validar título
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: |
    if [[ ! "$PR_TITLE" =~ ^(feat|fix|chore|docs|refactor|test)(\(.+\))?:\ .+ ]]; then
      echo "::error::Título no sigue Conventional Commits"; exit 1
    fi
```
- Lo mismo aplica a `actions/github-script` (usa `process.env`).

### Reusable workflows vs composite actions
- **Reusable workflow** (`on: workflow_call`): jobs completos con su propio `runs-on`, `environment` y permisos. Ideal para build de imagen y deploy compartidos entre servicios o repos.
- **Composite action**: secuencia de pasos dentro de un job (setup de toolchain). No puede declarar `environment` ni `permissions`.
- Pasa secretos explícitamente (`secrets: { REGISTRY_TOKEN: ... }`); `secrets: inherit` solo dentro del mismo repo/org confiable. Llama a workflows de otros repos por SHA.
- Referencias locales: `./.github/workflows/x.yml` y `./.github/actions/x`. Desde julio de 2026 GitHub admite además la sintaxis self-repository `$/...` (no depende del estado del checkout y cuenta para políticas de pinning; zizmor la sugiere). Verifica que tu versión de actionlint/GHES la soporte antes de adoptarla.

## Antipatrones
- `permissions: write-all` o sin bloque `permissions` (hereda el default del repo, a menudo write).
- `uses: org/action@main` o `@v1` de terceros sin SHA.
- Llaves estáticas de cloud en secrets; `echo ${{ secrets.X }}`; `set -x` con secretos.
- Deploy a producción en cada push sin environment ni aprobación.
- `pull_request_target` + `actions/checkout` con `ref: ${{ github.event.pull_request.head.sha }}`.
- Instalar dependencias sin lockfile (`npm install`, `pip install` suelto) en CI.
- Jobs sin `timeout-minutes`; matrices enormes para builds que solo corren en Linux.
- Construir la imagen dos veces (una para test, otra para push) en vez de promover el mismo digest entre entornos.

## Checklist final
- [ ] `permissions` mínimo a nivel workflow y ampliado por job.
- [ ] Todas las actions externas pinneadas por SHA con comentario de versión; Dependabot configurado.
- [ ] `concurrency` y `timeout-minutes` definidos.
- [ ] Caché del gestor de paquetes y de BuildKit.
- [ ] Sin `${{ }}` de datos de usuario dentro de `run:`.
- [ ] Deploy vía `environment` con aprobación para production; OIDC con `sub` restringido.
- [ ] Mismo digest de imagen promovido de staging a production.
- [ ] `actionlint` (y `zizmor` si está disponible) sin errores.

## Recursos
- [references/ci.md](references/ci.md): CI completos para Node/pnpm (Next.js, NestJS), Python/uv (FastAPI, LangGraph), matrices, service containers y monorepo. Léelo al crear `ci.yml`.
- [references/cd.md](references/cd.md): build + push a GHCR/ECR con attestations, reusable workflow, deploy por entornos a Kubernetes, OIDC para AWS/GCP/Azure, `terraform plan` en PR y builds de Expo con EAS. Léelo al crear `cd.yml`.
- `scripts/pin-actions.py`: resuelve `uses: owner/repo@tag` a SHA con `gh api` y deja la etiqueta como comentario. Uso desde la raíz del repo: `python3 "<carpeta de la skill github-actions>/scripts/pin-actions.py" .github` (dry-run) o con `--write` (reescribe). Usa etiquetas exactas (`v7.0.1`, no `v7`) antes de pinnear para que el comentario sea útil. Requiere `gh` autenticado.
- Validación: `actionlint` (`brew install actionlint` o `go install github.com/rhysd/actionlint/cmd/actionlint@latest`), `zizmor .github/workflows` (`uvx zizmor`).
- Skills relacionadas: `devops:docker`, `devops:kubernetes`, `devops:terraform`, `core:git-workflow`.
