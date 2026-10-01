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
| `provider "aws"`, `@aws-sdk/*`, `boto3`, `aws-cdk`, `cdk.json`, `aws-actions/*`; `provider "google"`, `@google-cloud/*`, `google-cloud-*`, `cloudbuild.yaml`, `google-github-actions/*` | Cloud (AWS / Google Cloud) | `devops:cloud-project-standard` (**obligatoria** cuando la tarea toca infraestructura, despliegue, IAM o servicios cloud) | `devops:cloud-architect` (diseño), `devops:iac-developer`, `devops:devops-engineer` |

Tabla completa de señales (lockfiles, archivos de config, variantes) en [references/stack-signals.md](references/stack-signals.md). Léela cuando el detector no sea concluyente o sea un monorepo.

Si un plugin de stack no está instalado, la skill no existe: sigue con las skills `core:*` y la documentación oficial.

### 3.1 Especialidades (alcance explícito)

Los comandos `/feature`, `/standard` e `/implement` aceptan una **especialidad** como primer argumento (`/standard front agregar filtro de pedidos`) para limitar el trabajo a un solo frente en lugar de autodetectar todos los stacks.

| Especialidad (alias) | Alcance | Skills (solo las que apliquen al stack detectado) | Agentes | Reviewer |
|---|---|---|---|---|
| `front` (`frontend`, `web`) | Next.js, React, TypeScript web | `frontend:nextjs-project-standard`, `frontend:nextjs-app-router`, `frontend:react-components`, `frontend:typescript-patterns`, `frontend:frontend-testing` | `frontend:nextjs-developer`, `frontend:react-developer`, `frontend:typescript-expert` | `frontend:frontend-reviewer` |
| `back` (`backend`, `api`) | NestJS, FastAPI, base de datos, contratos de API | `backend:nestjs-module`, `backend:fastapi-endpoint`, `backend:database-patterns`, `backend:backend-testing` | `backend:nestjs-developer`, `backend:fastapi-developer`, `backend:api-designer` | `backend:backend-reviewer` |
| `ia` (`ai`, `llm`) | LangChain, LangGraph, LangSmith | `backend:langchain-chains`, `backend:langchain-rag`, `backend:langgraph-agents`, `backend:langsmith-observability`, `backend:backend-testing` | `backend:langchain-developer`, `backend:langgraph-developer`, `backend:langsmith-specialist` | `backend:backend-reviewer` |
| `mobile` (`movil`) | Expo, React Native | `mobile:expo-project-standard`, `mobile:react-native-components`, `mobile:expo-router-navigation`, `mobile:mobile-state-data`, `mobile:mobile-testing` | `mobile:expo-developer`, `mobile:react-native-developer` | `mobile:mobile-reviewer` |
| `devops` (`infra`, `cloud`) | Docker, CI/CD, Kubernetes, Terraform, AWS / Google Cloud | `devops:cloud-project-standard` (obligatoria si la tarea toca infraestructura, despliegue o servicios cloud), `devops:docker`, `devops:github-actions`, `devops:kubernetes`, `devops:terraform` | `devops:devops-engineer`, `devops:iac-developer`, `devops:cloud-architect` (solo diseño) | `devops:security-auditor` |

Cómo aplicarla (los comandos remiten aquí):

1. **Parseo**: si la primera palabra de `$ARGUMENTS` (sin distinguir mayúsculas) es una especialidad o alias de la tabla, esa es la especialidad y el resto es la descripción. Si no coincide, no hay especialidad y todo funciona como siempre (autodetección). Si tras la especialidad no queda descripción, pídela y detente.
2. **Skills**: `core:*` de siempre + las de la fila, **filtradas por lo detectado** (en `front` sin Next.js no se cargan las `nextjs-*`; en `back` solo el framework presente).
3. **Agentes**: solo los de la fila, más los generales (`core:planner`, `core:architect`, `core:tester`, `core:documenter`). El review usa `core:reviewer` + el reviewer de la fila; no lances los de otros stacks.
4. **Frontera**: toca únicamente archivos de esa especialidad. Si la tarea necesita un cambio fuera (p. ej. un endpoint nuevo desde `front`), no lo hagas: déjalo como dependencia (qué contrato o cambio se necesita) y pregunta si se corre aparte con la otra especialidad.
5. **Verificación**: en monorepos, ejecuta los scripts (`lint`, `typecheck`, `test`, `build`) del proyecto de esa especialidad, no de todos.
6. **Sin señales**: si el repo no tiene nada de esa especialidad, dilo y pregunta antes de seguir (puede que falte el proyecto o que se refiera a otra).

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
- El comando `/feature` ejecuta el flujo completo; `/standard` hace lo mismo forzando los estándares completos (incluido el `*-project-standard` del stack) y verificando su checklist al final. Ambos, e `/implement`, aceptan una especialidad (`front`, `back`, `ia`, `mobile`, `devops`; ver 3.1) para acotar el trabajo a un solo frente.

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
