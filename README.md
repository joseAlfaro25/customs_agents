# My Agents

Suite de agentes, skills, comandos y hooks para frontend, backend, IA (LangChain), devops y mobile.
Fuente única en formato de plugins de Claude Code, compatible con **Codex, Cursor, GitHub Copilot, Gemini CLI** y cualquier herramienta que soporte [Agent Skills](https://agentskills.io) y `AGENTS.md`.

## Plugins

| Plugin | Para qué | Stack |
|---|---|---|
| **suite** | Instala todos los plugins de abajo de una vez (solo dependencias) | — |
| **core** | Agentes generales y la información compartida que usan todos | Cualquiera |
| **frontend** | Especialistas web | Next.js · React · TypeScript |
| **backend** | Especialistas de APIs e IA | NestJS · FastAPI · LangChain · LangGraph · LangSmith |
| **devops** | Contenedores, CI/CD e infraestructura | Docker · GitHub Actions · Kubernetes · Terraform |
| **mobile** | Apps móviles | React Native · Expo |

## Cómo funciona

```
                    ┌──────────── core:project-context ────────────┐
                    │  detecta stack + versiones, lee CLAUDE.md,   │
                    │  mapea tecnología → skill → especialista     │
                    └──────────────────────┬───────────────────────┘
                                           │ (todos los agentes lo cargan primero)
  core:planner → core:architect → core:coder / especialista → core:tester → core:reviewer → core:documenter
                  (si hay ADR)       frontend:* backend:*                     + reviewers
                                     mobile:*   devops:*                        de stack
```

- **Agentes generales (`core`)**: planificación, arquitectura, código, testing, review y documentación. Funcionan en cualquier stack porque cargan `core:project-context` y, a partir de ahí, las skills del stack detectado.
- **Especialistas (`frontend`, `backend`, `devops`, `mobile`)**: conocen a fondo una tecnología. Los agentes generales delegan en ellos cuando la tarea es de un solo stack.
- **Skills generales (`core`)**: estándares compartidos (código, planificación, arquitectura, testing, review, documentación, git).

## Estructura

```
install.sh                          # instalador de un comando (todas las IAs)
scripts/export.py                   # convierte la suite a Codex, Cursor, Copilot, Gemini, genérico
scripts/bump-version.py             # sube la versión de todos los plugins antes de publicar
docs/                               # guías para personas (no las cargan los agentes)
.claude-plugin/marketplace.json     # marketplace (lo leen Claude Code y Codex)
.agents/plugins/marketplace.json    # marketplace nativo de Codex
plugins/
├── suite/                          # plugin paraguas: dependencias = los 5 plugins
├── core/
│   ├── agents/    planner, architect, coder, tester, reviewer, documenter
│   ├── skills/    project-context, coding-standards, planning-method, architecture-principles,
│   │              testing-strategy, code-review-checklist, documentation-standards, git-workflow
│   ├── commands/  /plan, /design, /implement, /write-tests, /review, /document, /feature
│   └── hooks/     guard.py — pide confirmación antes de tocar secretos o correr comandos destructivos
├── frontend/
│   ├── agents/    nextjs-developer, react-developer, typescript-expert, frontend-reviewer
│   ├── skills/    nextjs-app-router, nextjs-project-standard, react-components, typescript-patterns,
│   │              frontend-testing
│   ├── commands/  /new-component, /new-page
│   └── hooks/     formatea con prettier local
├── backend/
│   ├── agents/    nestjs-developer, fastapi-developer, api-designer, backend-reviewer,
│   │              langchain-developer, langgraph-developer, langsmith-specialist
│   ├── skills/    nestjs-module, fastapi-endpoint, database-patterns, backend-testing,
│   │              langchain-chains, langchain-rag, langgraph-agents, langsmith-observability
│   ├── commands/  /new-nest-resource, /new-fastapi-router, /new-langgraph-agent
│   └── hooks/     formatea con ruff / prettier local
├── devops/
│   ├── agents/    devops-engineer, cloud-architect, iac-developer, security-auditor
│   ├── skills/    docker, github-actions, kubernetes, terraform
│   ├── commands/  /dockerize, /new-pipeline
│   └── hooks/     terraform fmt
└── mobile/
    ├── agents/    react-native-developer, expo-developer, mobile-reviewer
    ├── skills/    expo-project-standard, react-native-components, expo-router-navigation,
    │              mobile-state-data, mobile-testing
    ├── commands/  /new-screen
    └── hooks/     formatea con prettier local
```

Cada skill tiene su `SKILL.md` y, cuando hace falta, `references/` (material extenso que se lee bajo demanda) y `scripts/`.

## Instalación en un comando

```bash
curl -fsSL https://raw.githubusercontent.com/joseAlfaro25/customs_agents/main/install.sh | bash
```

Detecta qué IAs tienes (Claude Code, Codex, Cursor, Gemini CLI, Copilot) e instala **toda la suite** en cada una: agentes, skills, comandos, hooks e información general. Desde un clon del repo es lo mismo con `./install.sh`.

| Quiero... | Comando |
|---|---|
| Instalar todo en las IAs detectadas | `./install.sh` |
| Solo algunas herramientas | `./install.sh --tools claude,codex` |
| Además, configurar un proyecto (AGENTS.md, Copilot) | `./install.sh --project ~/mi-app` |
| Ver qué haría, sin ejecutar | `./install.sh --dry-run` |
| Actualizar | volver a ejecutar el mismo comando |
| Desinstalar todo | `./install.sh --uninstall` |

Qué hace en cada herramienta:

| Herramienta | Instala |
|---|---|
| Claude Code | marketplace + plugin `suite` (trae como dependencias los 5 plugins) |
| Codex | marketplace + los 5 plugins (skills y hook) + agentes en `~/.codex/agents`, comandos `$nombre` y bloque en `~/.codex/AGENTS.md` |
| Cursor | skills, agentes y comandos en `~/.cursor` |
| Gemini CLI | skills, agentes y comandos en `~/.gemini` + bloque en `~/.gemini/GEMINI.md` |
| Copilot / genérico | por proyecto con `--project`: `.github/{agents,skills,prompts}`, `.agents/skills` y `AGENTS.md` |

Requisitos: `git` y `python3`. Sin clon local, la suite se descarga en `~/.local/share/my-agents` (configurable con `MY_AGENTS_HOME`, y el repo con `MY_AGENTS_REPO`).

### Solo Claude Code, a mano

```bash
/plugin marketplace add joseAlfaro25/customs_agents     # o una ruta local
/plugin install suite@my-agents                         # instala los 5 plugins de una vez
```

También puedes instalar plugins sueltos (`core@my-agents`, `backend@my-agents`, ...). Instala siempre `core`: es la información general que usan todos.

**Para un equipo**: agrega esto al `.claude/settings.json` del repo y cada persona recibe la suite al confiar en el proyecto:

```json
{
  "extraKnownMarketplaces": {
    "my-agents": { "source": { "source": "github", "repo": "joseAlfaro25/customs_agents" } }
  },
  "enabledPlugins": { "suite@my-agents": true }
}
```

## Usar con otras IAs

`plugins/` es la **fuente única**. Las skills siguen el estándar abierto [Agent Skills](https://agentskills.io/specification), así que funcionan igual en todas las herramientas. Los agentes y comandos se convierten al formato de cada una con [`scripts/export.py`](scripts/export.py).

| Herramienta | Skills | Agentes | Comandos | Contexto general | Hooks |
|---|---|---|---|---|---|
| **Claude Code** | plugin | plugin | plugin (`/nombre`) | skill `core:project-context` | ✅ todos |
| **Codex** | plugin nativo (mismo marketplace) | export → `.codex/agents/*.toml` | export → skills (`$nombre`) | export → `AGENTS.md` | ✅ guard (`hooks/codex-hooks.json`) |
| **Cursor** | export → `.cursor/skills` | export → `.cursor/agents` | export → `.cursor/commands` | `AGENTS.md` | — |
| **GitHub Copilot** | export → `.github/skills` | export → `.github/agents/*.agent.md` | export → `.github/prompts` | `AGENTS.md` | — |
| **Gemini CLI** | export → `.gemini/skills` | export → `.gemini/agents` | export → `.gemini/commands/*.toml` | `GEMINI.md` | — |
| **Otras** (genérico) | export → `.agents/skills` | como skills `agent-<nombre>` | como skills `cmd-<nombre>` | `AGENTS.md` | — |

### Codex

Codex lee este mismo marketplace e instala los plugins de forma nativa (skills + hook de seguridad):

```bash
codex plugin marketplace add /ruta/a/My-Agents      # o usuario/repo de GitHub
codex plugin add core@my-agents                     # y frontend, backend, devops, mobile
# Agentes (.codex/agents) + comandos ($feature, $review...) + AGENTS.md en tu proyecto:
python3 /ruta/a/My-Agents/scripts/export.py --target codex --dest /ruta/a/tu-proyecto --skip-skills
```

Sin plugins, `--target codex` sin `--skip-skills` también copia las skills a `.agents/skills`.

### Cursor, Copilot, Gemini CLI y otras

```bash
python3 scripts/export.py --target cursor  --dest /ruta/a/tu-proyecto
python3 scripts/export.py --target copilot --dest /ruta/a/tu-proyecto
python3 scripts/export.py --target gemini  --dest /ruta/a/tu-proyecto
python3 scripts/export.py --target agents  --dest /ruta/a/tu-proyecto   # genérico
python3 scripts/export.py --target all     --dest /ruta/a/tu-proyecto   # todas
```

Opciones útiles:

| Opción | Qué hace |
|---|---|
| `--plugins core,backend` | Exporta solo esos plugins (incluye siempre `core`: es la información general) |
| `--user` | Instala en el home (`~/.codex`, `~/.agents`, `~/.cursor`, `~/.gemini`) para todos tus proyectos |
| `--dry-run` | Muestra qué generaría sin escribir |
| `--uninstall` | Elimina todo lo que generó para ese target |
| `--force` | Sobrescribe archivos existentes que no generó el script |

El export es **idempotente**: guarda qué generó en `<proyecto>/.my-agents/`, borra lo obsoleto en cada ejecución, no toca archivos tuyos y en `AGENTS.md`/`GEMINI.md` solo reemplaza el bloque entre `<!-- my-agents:start -->` y `<!-- my-agents:end -->`. Vuelve a ejecutarlo cada vez que actualices la suite.

Qué adapta el export:
- Nombres con prefijo (`core:project-context`) → sin prefijo (`project-context`) donde la herramienta no usa namespaces.
- `<carpeta de la skill X>` → la ruta real de la skill en esa herramienta.
- Herramientas de cada agente → equivalentes (`readonly`/`sandbox_mode = "read-only"` para reviewers, `tools` de Copilot y Gemini).
- `$ARGUMENTS` de los comandos → `{{args}}` en Gemini, o una nota con los argumentos en las demás.

## Uso rápido (Claude Code)

| Quiero... | Comando |
|---|---|
| Planear una tarea | `/plan agregar exportación de pedidos a CSV` |
| Diseñar / decidir arquitectura | `/design separar el agente de soporte en un servicio FastAPI` |
| Implementar | `/implement` (usa el plan de la conversación) |
| Escribir tests | `/write-tests` (sobre los cambios actuales) |
| Revisar | `/review` o `/review 123` (PR) |
| Documentar | `/document` |
| Todo el flujo | `/feature <descripción>` |

Si un nombre de comando choca con otro plugin, usa la forma con namespace: `/core:review`, `/backend:new-langgraph-agent`, etc.

También puedes invocar cualquier agente directamente, p. ej. *"usa el agente backend:langgraph-developer para..."*.

## Guías

- [Guía rápida: LangChain y LangGraph](docs/guia-langchain-langgraph.md): cuándo usar cada una, bloques básicos, estado y grafos, memoria, patrones (ReAct, router, human-in-the-loop), observabilidad, testing, agentes declarativos con `definition.json` y checklist de producción.

## Hooks

| Plugin | Evento | Qué hace |
|---|---|---|
| core | PreToolUse | (En Codex, bloquea con el motivo, porque Codex no soporta "ask".) Pide confirmación antes de editar `.env`, llaves o credenciales, y antes de `git push --force`, `reset --hard`, `terraform apply/destroy`, `kubectl apply/delete`, `docker push`, `eas build/submit/update`, SQL destructivo |
| frontend, mobile | PostToolUse | Formatea el archivo editado con el prettier del proyecto (si existe) |
| backend | PostToolUse | `ruff format` + `ruff check --fix` en `.py`; prettier en TS/JS |
| devops | PostToolUse | `terraform fmt` en `.tf` |

Los hooks de formato nunca bloquean: si la herramienta no está instalada, no hacen nada.

## Publicar cambios

1. `python3 scripts/bump-version.py` (patch; o `minor` / `major`): Claude Code y Codex cachean los plugins por versión.
2. Valida: `claude plugin validate .` y `claude plugin validate plugins/<nombre>`.
3. Commit y push. Los usuarios actualizan volviendo a ejecutar el instalador.

## Agregar un nuevo plugin

1. Crear `plugins/<nombre>/.claude-plugin/plugin.json` y `plugins/<nombre>/.codex-plugin/plugin.json` (con `"skills": "./skills/"` y `"hooks": "./hooks/codex-hooks.json"`).
2. Agregar `agents/`, `skills/`, `commands/`, `hooks/` según se necesite. Los agentes deben cargar `core:project-context` al inicio e incluir `Skill` en `tools`.
3. Añadir sus señales de detección y skills al mapa de `plugins/core/skills/project-context/SKILL.md`.
4. Registrarlo en `.claude-plugin/marketplace.json` y `.agents/plugins/marketplace.json`, añadirlo a `dependencies` de `plugins/suite`, a `PLUGINS` en `install.sh` y a `PLUGIN_ORDER` en `scripts/export.py`, y validar con `claude plugin validate plugins/<nombre>`.
5. Escribe rutas a scripts como `<carpeta de la skill X>/scripts/...` (nunca `${CLAUDE_PLUGIN_ROOT}`) para que funcionen en todas las herramientas.
