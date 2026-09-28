---
name: project-context
description: "Información general del proyecto: detecta el stack, lee CLAUDE.md y manifiestos, y mapea cada tecnología a la skill y agente especialista correctos. Cargar SIEMPRE al empezar cualquier tarea de código, planificación, arquitectura, testing, review o documentación."
---

# project-context

Punto de entrada común de todos los agentes. Antes de planear, diseñar, escribir, testear, revisar o documentar, hay que saber **qué proyecto es, con qué está hecho y qué reglas tiene**.

## 1. Leer las reglas del proyecto (en este orden)

1. `CLAUDE.md` en la raíz y en el directorio donde se va a trabajar (y `.claude/CLAUDE.md` si existe). Sus reglas **ganan** sobre cualquier convención de las skills.
2. `README.md`, `CONTRIBUTING.md`, `docs/` (sobre todo `docs/adr/` o `docs/architecture*`).
3. Configuración de calidad: `.editorconfig`, `eslint.config.*`/`.eslintrc*`, `prettier*`, `biome.json`, `ruff.toml`/`[tool.ruff]`, `mypy.ini`/`[tool.mypy]`, `tsconfig*.json`.
4. Historia reciente: `git log --oneline -15` para ver estilo de commits y en qué se está trabajando.

## 2. Detectar el stack

Ejecuta el detector incluido en esta skill (no modifica nada). La ruta es relativa a la carpeta de esta skill:

```bash
python3 "<carpeta de la skill project-context>/scripts/detect_stack.py" .
```

Devuelve: gestor de paquetes, tecnologías detectadas con su versión declarada, test runners, scripts disponibles (`dev`, `build`, `test`, `lint`, `typecheck`) y proyectos de un monorepo. Si no puedes ejecutar Python, revisa a mano los manifiestos de la tabla siguiente.

<!-- claude-only -->
> **Rutas de scripts**: en toda la suite, `<carpeta de la skill X>` es el directorio donde está instalada la skill `X` (el que contiene su `SKILL.md`), p. ej. `~/.claude/plugins/.../skills/X`, `.agents/skills/X`, `.cursor/skills/X` o `.github/skills/X` según la herramienta.
>
> **Nombres con prefijo**: `core:project-context`, `backend:fastapi-endpoint`, etc. usan el prefijo del plugin (así los nombra Claude Code). En otras herramientas la skill o el agente se llama igual sin prefijo (`project-context`, `fastapi-endpoint`).
<!-- /claude-only -->

**Las versiones mandan.** Nunca asumas una versión mayor: léela del manifiesto o del lockfile y adapta el código (p. ej. Next.js 14 vs 15+, Pydantic v1 vs v2, LangChain 0.x vs 1.x, Expo SDK).

## 3. Mapa tecnología → skill → agente especialista

| Señal en el repo | Tecnología | Skills a cargar | Agente especialista |
|---|---|---|---|
| `next` en dependencies, `next.config.*` | Next.js | `frontend:nextjs-app-router`, `frontend:react-components`, `frontend:nextjs-project-standard` (proyecto nuevo o sin convención definida) | `frontend:nextjs-developer` |
| `react` sin `next` ni `react-native` | React | `frontend:react-components` | `frontend:react-developer` |
| `tsconfig.json`, `typescript` | TypeScript | `frontend:typescript-patterns` | `frontend:typescript-expert` |
| `vitest`, `jest`, `@testing-library/*`, `@playwright/test` (web) | Tests frontend | `frontend:frontend-testing` | `core:tester` |
| `@nestjs/core` | NestJS | `backend:nestjs-module` | `backend:nestjs-developer` |
| `fastapi` en `pyproject.toml`/`requirements*.txt` | FastAPI | `backend:fastapi-endpoint` | `backend:fastapi-developer` |
| `prisma/`, `typeorm`, `sqlalchemy`, `alembic/` | Base de datos | `backend:database-patterns` | según framework |
| `pytest`, `@nestjs/testing`, `supertest` | Tests backend | `backend:backend-testing` | `core:tester` |
| `langchain*`, `@langchain/*` | LangChain | `backend:langchain-chains`, `backend:langchain-rag` (si hay vector store/retriever) | `backend:langchain-developer` |
| `langgraph`, `@langchain/langgraph`, `langgraph.json` | LangGraph | `backend:langgraph-agents` | `backend:langgraph-developer` |
| `langsmith`, variables `LANGSMITH_*` / `LANGCHAIN_TRACING*` | LangSmith | `backend:langsmith-observability` | `backend:langsmith-specialist` |
| Diseño de endpoints / contratos OpenAPI | API | — | `backend:api-designer` |
| `expo`, `react-native`, `app.json`, `eas.json` | Mobile | `mobile:react-native-components`, `mobile:expo-router-navigation`, `mobile:mobile-state-data`, `mobile:expo-project-standard` (proyecto nuevo o sin convención definida) | `mobile:expo-developer`, `mobile:react-native-developer` |
| `jest-expo`, `.maestro/`, `detox` | Tests mobile | `mobile:mobile-testing` | `core:tester` |
| `Dockerfile`, `compose*.yml` | Docker | `devops:docker` | `devops:devops-engineer` |
| `.github/workflows/` | CI/CD | `devops:github-actions` | `devops:devops-engineer` |
| `Chart.yaml`, `kustomization.yaml`, manifiestos `apiVersion:` | Kubernetes | `devops:kubernetes` | `devops:devops-engineer` |
| `*.tf` | Terraform | `devops:terraform` | `devops:iac-developer` |

Tabla completa de señales (lockfiles, archivos de config, variantes) en [references/stack-signals.md](references/stack-signals.md). Léela cuando el detector no sea concluyente o sea un monorepo.

Si un plugin de stack no está instalado, la skill no existe: sigue con las skills `core:*` y la documentación oficial.

## 4. Skills generales (aplican a todo stack)

| Necesidad | Skill |
|---|---|
| Escribir o modificar código | `core:coding-standards` |
| Descomponer y planear una tarea | `core:planning-method` |
| Decisiones de diseño, límites de módulos, ADRs | `core:architecture-principles` |
| Qué y cómo testear | `core:testing-strategy` |
| Revisar cambios | `core:code-review-checklist` |
| README, ADR, docs de API, comentarios | `core:documentation-standards` |
| Ramas, commits, PRs | `core:git-workflow` |

## 5. Flujo entre agentes generales

```
core:planner → core:architect (si hay decisiones de diseño) → core:coder / especialista
             → core:tester → core:reviewer → core:documenter
```

- Cada agente general **delega en el especialista de stack** cuando la tarea es 100 % de una tecnología (p. ej. un router FastAPI nuevo → `backend:fastapi-developer`) y actúa como coordinador cuando cruza varias (p. ej. endpoint + pantalla web + pantalla mobile).
- El comando `/feature` ejecuta el flujo completo.

## 6. Resumen de contexto (salida de esta skill)

Antes de trabajar, deja claro (para ti o en tu respuesta):

```markdown
**Contexto**
- Proyecto(s): <app web / api / mobile / infra; monorepo sí/no>
- Stack: <tecnología@versión, ...>
- Gestor de paquetes: <pnpm | npm | yarn | bun | uv | poetry | pip>
- Comandos de verificación: <typecheck> · <lint> · <test> · <build>
- Reglas del proyecto relevantes: <de CLAUDE.md / config>
- Skills a usar: <lista con namespace>
```

## Reglas

- No instales dependencias nuevas ni cambies versiones sin que la tarea lo pida o el usuario lo apruebe.
- Usa el gestor de paquetes del lockfile existente (`pnpm-lock.yaml` → pnpm, `uv.lock` → uv, etc.). Nunca mezcles.
- Si el proyecto ya tiene una convención (estructura, naming, librería de estado, ORM), **síguela** aunque la skill sugiera otra.
- Si falta información clave (qué app del monorepo, qué entorno), pregunta antes de asumir.
