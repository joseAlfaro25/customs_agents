---
description: "Genera un agente LangGraph (estado tipado, nodos, grafo, checkpointer, human-in-the-loop opcional, tests con modelo fake y tracing LangSmith) integrado en el backend del proyecto"
argument-hint: "<nombre-agente> [descripción del objetivo del agente]"
---

Genera un agente LangGraph a partir de: `$ARGUMENTS`

## 1. Validar el argumento
- El primer token de `$ARGUMENTS` es el nombre del agente; el resto, la descripción de su objetivo. Si `$ARGUMENTS` está vacío, **detente y pide** nombre y objetivo (qué recibe, qué produce, qué tools necesita, si requiere aprobación humana).
- Normaliza: paquete en snake_case (`support_triage`), nombre de grafo en kebab-case para `langgraph.json`/endpoints (`support-triage`).
- Si falta la descripción, pregunta por el objetivo antes de diseñar; no inventes el comportamiento.

## 2. Cargar contexto y skills
1. Carga `core:project-context`; lee `CLAUDE.md`, manifiestos (`pyproject.toml` o `package.json`), `langgraph.json` si existe y agentes existentes (`grep -rn "StateGraph\|create_agent" .`).
2. Carga `backend:langgraph-agents`, `backend:langchain-chains`, `backend:langsmith-observability` y `backend:backend-testing`. Si el agente consulta documentos, carga también `backend:langchain-rag`.
3. Detecta versiones reales de `langgraph`, `langchain`, `langchain-core`, proveedor de modelo y checkpointer (`langgraph-checkpoint-postgres`). Si alguna API que vas a usar no está en las skills o tienes dudas, verifícala en `docs.langchain.com` antes de escribir.
4. Lenguaje: Python por defecto; si el backend es NestJS/TypeScript, usa `@langchain/langgraph` siguiendo los equivalentes JS de la skill.
5. Si faltan dependencias, propón añadirlas con el gestor del proyecto (`uv add langgraph langchain langchain-<proveedor>`), indicando versiones.

## 3. Diseñar (mostrar antes de implementar)
- Decide si basta `create_agent` (modelo + tools en bucle, con middleware) o se necesita un `StateGraph` propio (pasos deterministas, ramas, HITL en puntos concretos). Justifica.
- Presenta un diagrama Mermaid del grafo, la tabla de nodos (qué leen/escriben), el esquema del estado (con reducers), el `Context` (user_id, tenant, etc.), tools y puntos de `interrupt`.

## 4. Implementar
Estructura (ajústala a la del proyecto):
```
app/agents/<nombre>/
├── state.py     # State (TypedDict/MessagesState + reducers), Context (dataclass)
├── prompts.py   # system prompts (o carga desde LangSmith si el proyecto versiona prompts)
├── tools.py     # @tool tipadas, con ToolRuntime para el contexto del usuario
├── nodes.py     # nodos async y funciones de routing tipadas con Literal/Command
└── graph.py     # build_graph(model, checkpointer=None, store=None) + graph para langgraph.json
```
1. **Estado y contexto** tipados; reducers en campos compartidos; nada no serializable.
2. **Modelo** inyectado a `build_graph` (factory desde settings con `init_chat_model`, `timeout`, `max_retries`) para poder usar un fake en tests.
3. **Nodos** pequeños que devuelven actualizaciones parciales; límites de iteración (`recursion_limit`, contadores o `ModelCallLimitMiddleware`).
4. **HITL** si el objetivo incluye acciones con efectos: `interrupt(payload)` en un nodo dedicado (idempotente, sin `try/except` genérico alrededor) o `HumanInTheLoopMiddleware` si es `create_agent`.
5. **Checkpointer**: `InMemorySaver` solo en tests; en la app, `AsyncPostgresSaver` creado una vez en el `lifespan` (FastAPI) o provider (Nest) con `setup()`.
6. **Integración HTTP** (si el proyecto es una API): endpoints `POST /agents/<nombre>/threads/{thread_id}/runs` (JSON o SSE con `astream(..., stream_mode=["updates","messages"], version="v2")`) y `POST .../resume` con `Command(resume=...)`, validando que el thread pertenece al usuario. Si existe `langgraph.json`, registra el grafo ahí en su lugar o además, según la convención del proyecto.
7. **Tracing LangSmith**: `run_name="<nombre>"`, `tags` (feature, versión de prompt) y `metadata` (user_id, thread_id) en cada invocación; añade `LANGSMITH_*` a settings y `.env.example` si no existen.

## 5. Tests
En `tests/agents/<nombre>/`:
- `test_nodes.py`: cada nodo y función de routing con estados construidos a mano.
- `test_graph.py`: flujo completo con modelo fake (`GenericFakeChatModel` con `bind_tools` si hay tools) + `InMemorySaver`; si hay HITL, verifica `__interrupt__` y la reanudación con `Command(resume=...)`.
- Tests del endpoint con la dependencia del grafo sobreescrita.
- Tracing desactivado en tests (`LANGSMITH_TRACING=false`).
- Opcional: dataset pequeño y script de evaluación en `tests/evals/` o `app/agents/<nombre>/eval.py` (fuera del suite rápido).

## 6. Verificar
1. `ruff check .` y `ruff format --check .` (o `npx tsc --noEmit` y `npm run lint` en TS).
2. Typecheck si está configurado.
3. `pytest tests/agents/<nombre> -q` (o `npm test -- <nombre>`).
4. Si hay credenciales y el usuario lo permite, una ejecución real de humo con tracing activo y comparte el nombre del proyecto LangSmith donde quedó la traza.

## 7. Entregar
Diagrama del grafo, estado y contexto, archivos creados/modificados, cómo invocarlo (snippet y endpoint), cómo reanudar interrupts, configuración nueva (env vars, dependencias), resultado de las verificaciones y riesgos (coste, bucles, APIs beta).
