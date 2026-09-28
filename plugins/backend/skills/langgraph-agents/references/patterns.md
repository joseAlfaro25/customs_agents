# Patrones avanzados de LangGraph

Verifica la versión de `langgraph`/`langchain` instalada antes de copiar.

## 1. Subgrafos

### Estado compartido: subgrafo compilado como nodo
```python
research = build_research_graph()          # usa las mismas claves (p. ej. "messages")
builder.add_node("research", research)
```

### Estado distinto: invocar dentro de un nodo y transformar
```python
async def run_research(state: State) -> dict:
    out = await research.ainvoke({"query": state["messages"][-1].text})
    return {"documents": out["documents"]}
```

### Persistencia de subgrafos
- Por defecto (`compile()` sin checkpointer) el subgrafo hereda el checkpointer del padre dentro de cada invocación: soporta interrupts, pero no acumula memoria propia entre llamadas.
- `compile(checkpointer=True)`: memoria por thread del subgrafo (asistentes que acumulan contexto propio).
- `compile(checkpointer=False)`: sin checkpointing (función pura, más barato).
- Streaming con `subgraphs=True`; `graph.get_state(cfg, subgraphs=True)` para inspeccionar estado anidado.

## 2. Multi-agente

Orden de preferencia (de más simple a más complejo): un solo agente con buenas tools → **router** determinista → **subagentes como tools** (supervisor) → **handoffs** → workflow custom.

### Subagentes como tools (supervisor)
```python
from langchain.agents import create_agent
from langchain.tools import tool

billing_agent = create_agent(model, tools=[get_invoice, refund_order],
                             system_prompt="Especialista en facturación.", name="billing")
tech_agent = create_agent(model, tools=[search_kb, create_ticket],
                          system_prompt="Especialista técnico.", name="tech")

@tool("billing", description="Resuelve dudas de facturas, cobros y reembolsos")
async def call_billing(request: str) -> str:
    result = await billing_agent.ainvoke({"messages": [{"role": "user", "content": request}]})
    return result["messages"][-1].text

@tool("tech", description="Resuelve problemas técnicos del producto")
async def call_tech(request: str) -> str:
    result = await tech_agent.ainvoke({"messages": [{"role": "user", "content": request}]})
    return result["messages"][-1].text

supervisor = create_agent(model, tools=[call_billing, call_tech],
                          system_prompt="Delega en el especialista adecuado y sintetiza la respuesta.",
                          checkpointer=checkpointer)
```
- El supervisor controla el contexto: cada subagente recibe solo la petición, no todo el historial (menos tokens, menos confusión).
- Para propagar contexto del usuario, usa `ToolRuntime` en la tool y pásalo como `context=` al subagente.
- `langgraph-supervisor` y `langgraph-swarm` fueron librerías auxiliares populares; la documentación actual de LangChain 1.x presenta estos patrones con `create_agent` y tools. Si el proyecto ya las usa, verifica su estado de mantenimiento antes de extenderlas.

### Router determinista
```python
class Route(BaseModel):
    target: Literal["billing", "tech", "general"]

router_model = model.with_structured_output(Route)

async def route(state: State) -> Command[Literal["billing", "tech", "general"]]:
    r = await router_model.ainvoke(state["messages"])
    return Command(goto=r.target)
```
Cada destino puede ser un `create_agent` compilado añadido como nodo; con `Send` puedes consultar varios en paralelo y sintetizar después.

### Handoffs (traspaso de control entre agentes del grafo padre)
```python
from langgraph.types import Command

@tool
def transfer_to_billing(runtime: ToolRuntime) -> Command:
    """Transfiere la conversación al agente de facturación."""
    return Command(
        goto="billing",
        graph=Command.PARENT,                      # navega en el grafo padre
        update={"messages": [ToolMessage("Transferido a facturación", tool_call_id=runtime.tool_call_id)],
                "active_agent": "billing"},
    )
```
Úsalo cuando el usuario deba seguir hablando directamente con el especialista. Guarda `active_agent` en el estado para retomar en el siguiente turno.

## 3. Memoria a largo plazo (Store)
```python
from langgraph.store.postgres.aio import AsyncPostgresStore

async def remember(state: State, runtime: Runtime[Context]) -> dict:
    ns = ("memories", runtime.context.user_id)
    await runtime.store.aput(ns, key=str(uuid4()), value={"fact": "prefiere respuestas cortas"})
    items = await runtime.store.asearch(ns, query="preferencias", limit=5)   # búsqueda semántica si el store tiene index
    return {}

async with AsyncPostgresStore.from_conn_string(url) as store:
    await store.setup()
    graph = build_graph(checkpointer=checkpointer, store=store)
```
Para búsqueda semántica el store se crea con `index={"embed": embeddings, "dims": 1536}`; verifica la firma en tu versión.

## 4. Integración con FastAPI (threads, runs, resume)
```python
@router.post("/threads/{thread_id}/runs")
async def run(thread_id: UUID, body: RunIn, graph: GraphDep, user: CurrentUser):
    await ensure_thread_owner(thread_id, user.id)
    cfg = {"configurable": {"thread_id": str(thread_id)},
           "run_name": "support_graph", "metadata": {"user_id": str(user.id)}}
    out = await graph.ainvoke({"messages": [{"role": "user", "content": body.message}]}, cfg,
                              context=Context(user_id=str(user.id), tenant_id=user.tenant_id))
    if "__interrupt__" in out:
        return {"status": "interrupted", "interrupts": [{"id": i.id, "value": i.value} for i in out["__interrupt__"]]}
    return {"status": "done", "answer": out["messages"][-1].text}

@router.post("/threads/{thread_id}/resume")
async def resume(thread_id: UUID, body: ResumeIn, graph: GraphDep, user: CurrentUser):
    await ensure_thread_owner(thread_id, user.id)
    cfg = {"configurable": {"thread_id": str(thread_id)}}
    state = await graph.aget_state(cfg)
    if not state.next:
        raise ConflictError("Thread has no pending interrupt")
    out = await graph.ainvoke(Command(resume=body.decision), cfg,
                              context=Context(user_id=str(user.id), tenant_id=user.tenant_id))
    return {"status": "done", "answer": out["messages"][-1].text}
```
- El grafo y el checkpointer se crean en `lifespan` (ver `backend:fastapi-endpoint`).
- Tabla propia `threads(id, user_id, created_at, title)` para propiedad y listados; el checkpointer no es un modelo de dominio.

## 5. Despliegue

### LangSmith Deployment / Agent Server (antes LangGraph Platform)
`langgraph.json` en la raíz:
```json
{
  "dependencies": ["."],
  "graphs": { "support": "./app/agents/support/graph.py:graph" },
  "env": ".env",
  "python_version": "3.12"
}
```
- Desarrollo local: `uv add --dev "langgraph-cli[inmem]"` y `langgraph dev` (servidor en memoria + Studio). Requiere Python ≥ 3.11.
- El servidor gestiona checkpointer, store, threads, runs, cola y streaming; exporta el grafo **sin** checkpointer propio (lo inyecta la plataforma).
- Cliente: `from langgraph_sdk import get_client` → `client.runs.stream(thread_id, "support", input=..., stream_mode="updates")`.
- `langgraph build` genera una imagen Docker para self-hosting; revisa los requisitos de licencia/infra de la opción elegida.

### Self-hosted dentro de tu API
Grafo compilado en lifespan + `AsyncPostgresSaver` + endpoints propios (sección 4). Más control, pero tú gestionas colas, reintentos, cancelación y escalado horizontal (el checkpointer en Postgres permite múltiples réplicas).

### Producción
- Timeouts por nodo/llamada al modelo; LangGraph 1.2 añadió timeouts y manejadores de error a nivel de nodo (consulta la API exacta en la documentación de tu versión).
- `recursion_limit` explícito, límites de coste (middleware en `create_agent`), métricas de latencia/tokens en LangSmith.
- Migraciones del checkpointer al actualizar `langgraph-checkpoint-postgres` (`setup()` aplica las pendientes).

## 6. Equivalentes JS/TS (LangGraph.js 1.x)
```ts
import { StateSchema, MessagesValue, StateGraph, START, END, Command, interrupt, MemorySaver } from '@langchain/langgraph';
import { z } from 'zod/v4';

const State = new StateSchema({
  messages: MessagesValue,
  intent: z.enum(['refund', 'question', 'other']).optional(),
});

const graph = new StateGraph(State)
  .addNode('classify', classify)
  .addNode('answer', answer)
  .addEdge(START, 'classify')
  .addConditionalEdges('classify', (s) => (s.intent === 'question' ? 'answer' : END))
  .addEdge('answer', END)
  .compile({ checkpointer: new MemorySaver() });

// HITL
const decision = interrupt({ question: '¿Aprobar?' });       // dentro de un nodo
await graph.invoke(new Command({ resume: { approved: true } }), { configurable: { thread_id } });
```
- Versiones anteriores de LangGraph.js usan `Annotation.Root({...})` y `MessagesAnnotation`; sigue lo que ya use el proyecto.
- Checkpointer Postgres: `@langchain/langgraph-checkpoint-postgres` (`PostgresSaver.fromConnString(url)` + `await saver.setup()`).
- En NestJS, construye el grafo en un provider `useFactory` y exponlo con un token (ver `backend:langchain-chains`, referencia de integración).
