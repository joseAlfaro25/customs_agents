---
name: langsmith-observability
description: "Tracing y evaluación con LangSmith: env vars, @traceable y wrappers, proyectos, metadata y tags, datasets, evaluate() y evaluadores (heurísticos y LLM-as-judge), experimentos, pytest, prompts versionados y monitoreo en producción. Usar al instrumentar, depurar o evaluar apps LLM."
---

# langsmith-observability

## Objetivo
Hacer observable y medible cualquier aplicación LLM del backend: trazas completas y filtrables, datasets representativos, evaluadores confiables, experimentos comparables y un circuito de monitoreo y feedback en producción.

## Cuándo aplicarla
- Activar tracing en un servicio LangChain/LangGraph o en código que usa SDKs de proveedores directamente.
- Depurar una respuesta mala, lenta o cara a partir de su traza.
- Crear un dataset y evaluar un cambio de prompt, modelo, chunking o grafo.
- Añadir evaluaciones a CI o monitoreo online en producción.
- Versionar prompts fuera del código.

## Antes de empezar
1. Carga `core:project-context`. **Verifica la versión en el manifiesto del proyecto**: `langsmith` (Python/JS), `langchain-core`, `openevals`/`agentevals` si se usan. La integración pytest requiere `langsmith>=0.3.4` (`langsmith[pytest]`).
2. Nombres de variables: los actuales son `LANGSMITH_*`; las antiguas `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` siguen reconociéndose en muchas versiones, pero no las mezcles en código nuevo.
3. Ante dudas de parámetros (`evaluate`, `Client`, filtros), verifica en `docs.langchain.com/langsmith/`.

## Configuración
```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...                 # secreto: gestor de secretos, nunca en el repo
LANGSMITH_PROJECT=myapp-dev                # un proyecto por app y entorno
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com   # solo si no es la región US o self-hosted
LANGSMITH_WORKSPACE_ID=...                 # si la API key tiene acceso a varios workspaces
```
- Añade estas claves a `Settings` (pydantic-settings) o al esquema de `ConfigModule` y a `.env.example` con placeholders.
- En tests unitarios: `LANGSMITH_TRACING=false`.
- Proyecto dinámico en runtime: `with ls.tracing_context(project_name="myapp-batch", enabled=True): ...` (Python) o `new LangChainTracer({ projectName })` como callback (JS).

## Tracing de LangChain y LangGraph
Con las env vars activas, modelos, cadenas, agentes y grafos se trazan solos. Añade contexto en `config`:
```python
await agent.ainvoke(
    inputs,
    config={
        "run_name": "support_chat",
        "tags": ["feature:support", f"prompt:{PROMPT_VERSION}"],
        "metadata": {"user_id": user.id, "tenant_id": user.tenant_id, "thread_id": thread_id},
        "configurable": {"thread_id": thread_id},
    },
)
```
- `tags` para categorías de baja cardinalidad (feature, versión); `metadata` para IDs y datos de filtrado.
- Los threads de conversación se agrupan en la UI si la metadata incluye `thread_id` (o `session_id`/`conversation_id`).

## Tracing de código propio
```python
import langsmith as ls
from langsmith import traceable
from langsmith.wrappers import wrap_anthropic   # o wrap_openai
import anthropic

client = wrap_anthropic(anthropic.AsyncAnthropic())

@traceable(run_type="retriever", name="search_kb")
async def search_kb(query: str) -> list[dict]:
    ...

@traceable(name="answer_question", tags=["rag"])
async def answer_question(question: str, user_id: str) -> str:
    docs = await search_kb(question)                     # queda anidado como hijo
    ...

await answer_question(q, user_id, langsmith_extra={"metadata": {"user_id": user_id}})
```
- `run_type`: `chain` (default), `llm`, `tool`, `retriever`, `prompt`, `embedding`, `parser`.
- Bloques sin función: `with ls.trace("postprocess", "chain", inputs={...}) as rt: ... rt.end(outputs={...})`.
- ID de run propio (para asociar feedback): `run_id = ls.uuid7()` y `langsmith_extra={"run_id": run_id}`; verifica que tu versión exporte `uuid7` (si no, usa `uuid.uuid4()`).
- JS: `import { traceable } from "langsmith/traceable"; const fn = traceable(async (q: string) => ..., { name: "answer_question", run_type: "chain" });` y `wrapOpenAI` de `langsmith/wrappers`.

## Flush de trazas
Las trazas se envían en background; en scripts, jobs y serverless hay que esperar antes de salir:
- LangChain Python: `from langchain_core.tracers.langchain import wait_for_all_tracers; wait_for_all_tracers()`.
- `@traceable` con un `Client` propio: pásalo con `@traceable(client=client)` y llama a `client.flush()` al terminar.
- JS: `await awaitAllCallbacks()` (`@langchain/core/callbacks/promises`) y, en serverless, `LANGCHAIN_CALLBACKS_BACKGROUND=false`.
- Servidores FastAPI/Nest de larga vida no lo necesitan por request; hazlo en el shutdown (`lifespan`/`onApplicationShutdown`).

## Privacidad y coste
- No envíes secretos ni PII innecesaria: usa las opciones del `Client` para ocultar inputs/outputs (`hide_inputs`/`hide_outputs`, o `LANGSMITH_HIDE_INPUTS`/`LANGSMITH_HIDE_OUTPUTS`) o anonimizadores; verifica los nombres en tu versión.
- Alto volumen: muestreo (`LANGSMITH_TRACING_SAMPLING_RATE`, verifica disponibilidad) o tracing condicional con `tracing_context(enabled=...)`.

## Datasets y evaluación (resumen)
```python
from langsmith import Client

client = Client()
ds = client.create_dataset(dataset_name="support-triage-v1", description="Tickets reales etiquetados")
client.create_examples(dataset_id=ds.id, examples=[
    {"inputs": {"ticket": "No puedo pagar con tarjeta"}, "outputs": {"category": "billing"}},
])

def target(inputs: dict) -> dict:
    return {"category": triage_chain.invoke(inputs["ticket"]).category}

def exact_category(outputs: dict, reference_outputs: dict) -> bool:
    return outputs["category"] == reference_outputs["category"]

results = client.evaluate(
    target,
    data="support-triage-v1",
    evaluators=[exact_category],
    experiment_prefix="triage-sonnet-promptv3",
    metadata={"model": settings.llm_model, "prompt_version": "v3"},
    max_concurrency=4,
)
```
- Evaluadores reciben por nombre `inputs`, `outputs`, `reference_outputs` (también `run`, `example`) y devuelven `bool`, número o `{"key", "score", "comment"}`.
- Async: `from langsmith import aevaluate` para targets async y datasets grandes.
- Fuentes de ejemplos: casos reales de producción (desde trazas, anotados), casos límite y fallos conocidos. Versiona el dataset y usa splits (`train`/`test`) o tags.

Evaluadores LLM-as-judge (`openevals`), evaluación de trayectorias de agentes (`agentevals`), evaluadores de resumen, `num_repetitions`, comparación de experimentos, pytest/Vitest, prompts versionados, feedback y monitoreo online: lee [references/evaluation-and-monitoring.md](references/evaluation-and-monitoring.md).

## Prompts versionados (resumen)
```python
prompt = client.pull_prompt("support-system:prod")           # tag o commit hash, no la versión flotante
chain = client.pull_prompt("support-triage", include_model=True)   # prompt + modelo configurado
client.push_prompt("support-system", object=prompt_template)
```
Cachea el prompt en memoria con TTL; ten un fallback local si LangSmith no responde.

## Antipatrones
- API key en el código o en `.env` commiteado; tracing activo en unit tests.
- Todo en el proyecto `default`; sin `metadata` para filtrar por usuario/tenant.
- Evaluar con 5 ejemplos inventados; cambiar varias variables en un mismo experimento.
- Confiar en un LLM-as-judge sin calibrarlo contra etiquetas humanas.
- Scripts/serverless que terminan sin flush (trazas perdidas).
- Prompts de producción referenciados sin tag/commit.

## Checklist final
- [ ] Env vars en settings y `.env.example`; proyecto por entorno.
- [ ] `run_name`, `tags` y `metadata` (user/tenant/thread) en las invocaciones principales.
- [ ] Código no-LangChain con `@traceable`/wrappers; flush en jobs y shutdown.
- [ ] PII/secretos ocultos según política.
- [ ] Dataset versionado y evaluadores con nombres estables.
- [ ] Experimento ejecutado con metadata (modelo, prompt, commit) y resultados revisados.
- [ ] Feedback de usuario y monitoreo online definidos para producción.
