# Plantillas de CI

Todas usan SHAs verificados el 2026-09-28 (ver tabla en SKILL.md). Vuelve a verificarlos con `scripts/pin-actions.py` antes de entregar. Adapta los comandos a los scripts reales del proyecto.

## 1. Node + pnpm (Next.js / NestJS)

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: pnpm/action-setup@ea17c68df8912ef543352723c149a84f56e3d413 # v6.1.0
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: .nvmrc
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm typecheck

  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        node: [22, 24]
    services:
      postgres:
        image: postgres:18
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U test"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
    env:
      DATABASE_URL: postgresql://test:test@localhost:5432/test
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: pnpm/action-setup@ea17c68df8912ef543352723c149a84f56e3d413 # v6.1.0
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version: ${{ matrix.node }}
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - run: pnpm test -- --coverage

  build:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: [lint, test]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: pnpm/action-setup@ea17c68df8912ef543352723c149a84f56e3d413 # v6.1.0
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: .nvmrc
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - run: pnpm build
        env:
          NEXT_TELEMETRY_DISABLED: "1"
      # Construye la imagen sin publicar para detectar roturas del Dockerfile en el PR
      - uses: docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4.4.1
      - uses: docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc # v7.4.0
        with:
          context: .
          push: false
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Notas:
- Si el proyecto no tiene `.nvmrc`, usa `node-version: 24` o `node-version-file: package.json` (lee `engines.node` / `devEngines`).
- La matriz de Node solo tiene sentido en librerías; para una app basta la versión de producción.
- Con npm: elimina `pnpm/action-setup`, usa `cache: npm` y `npm ci`.
- Next.js: cachea `.next/cache` con `actions/cache` (key con hash del lockfile y de los fuentes) si los builds son lentos.

## 2. Python + uv (FastAPI / LangChain / LangGraph)

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy .   # o pyright, según el proyecto

  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        python: ["3.13", "3.14"]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
          python-version: ${{ matrix.python }}
      - run: uv sync --locked
      - run: uv run pytest --cov --cov-report=xml
        env:
          # Tests de LangChain/LangGraph: usa fakes/mocks; no llames a LLMs reales en CI de PR
          LANGSMITH_TRACING: "false"
```

Notas:
- `uv sync` instala el grupo `dev` por defecto; `--locked` falla si `uv.lock` no está al día con `pyproject.toml`.
- Si el proyecto usa pip: `actions/setup-python` con `python-version-file: .python-version`, `cache: pip`, `cache-dependency-path: requirements*.txt` y `pip install -r requirements-dev.txt`.
- Evals con LLM reales (LangSmith) van en un workflow aparte, manual o nocturno, con secretos en un environment `evals`.

## 3. Monorepo con filtros de ruta

```yaml
jobs:
  changes:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
      pull-requests: read
    outputs:
      web: ${{ steps.filter.outputs.web }}
      api: ${{ steps.filter.outputs.api }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: dorny/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d # v4.0.3
        id: filter
        with:
          filters: |
            web:
              - 'apps/web/**'
              - 'packages/**'
            api:
              - 'apps/api/**'

  web:
    needs: changes
    if: needs.changes.outputs.web == 'true'
    uses: ./.github/workflows/_node-ci.yml
    with:
      working-directory: apps/web

  api:
    needs: changes
    if: needs.changes.outputs.api == 'true'
    uses: ./.github/workflows/_python-ci.yml
    with:
      working-directory: apps/api

  # Check requerido único para branch protection: pasa si los jobs pasaron o se saltaron
  ci-ok:
    if: always()
    needs: [web, api]
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - run: |
          if [[ "${{ contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') }}" == "true" ]]; then
            exit 1
          fi
```
Con Turborepo/Nx puedes delegar el filtrado a `turbo run lint test build --filter=...[origin/main]` (requiere `fetch-depth: 0`).

## 4. Composite action para setup repetido

`.github/actions/setup-node-pnpm/action.yml`:
```yaml
name: Setup Node + pnpm
description: Instala pnpm, Node y dependencias con caché
inputs:
  working-directory:
    description: Directorio del paquete
    default: "."
runs:
  using: composite
  steps:
    - uses: pnpm/action-setup@ea17c68df8912ef543352723c149a84f56e3d413 # v6.1.0
      with:
        package_json_file: ${{ inputs.working-directory }}/package.json
    - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
      with:
        node-version-file: ${{ inputs.working-directory }}/.nvmrc
        cache: pnpm
        cache-dependency-path: ${{ inputs.working-directory }}/pnpm-lock.yaml
    - shell: bash
      working-directory: ${{ inputs.working-directory }}
      run: pnpm install --frozen-lockfile
```

## 5. Dependabot para actions

`.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    groups:
      actions:
        patterns: ["*"]
  - package-ecosystem: docker
    directory: /
    schedule:
      interval: weekly
```
Añade `npm`/`uv`/`pip` según el stack (Dependabot soporta `uv` como ecosistema; verifica en la documentación vigente).
