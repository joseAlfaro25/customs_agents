# Evaluación avanzada y monitoreo con LangSmith

Verifica la versión de `langsmith`, `openevals` y `agentevals` instalada antes de copiar.

## 1. LLM-as-judge con openevals
```python
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT

correctness_judge = create_llm_as_judge(
    prompt=CORRECTNESS_PROMPT,
    model=settings.judge_model,          # p. ej. "openai:..." o "anthropic:..."; mejor distinto del evaluado
    feedback_key="correctness",
)

def correctness(inputs: dict, outputs: dict, reference_outputs: dict):
    return correctness_judge(inputs=inputs, outputs=outputs, reference_outputs=reference_outputs)
```
`openevals` incluye prompts prearmados (corrección, concisión, alucinación, RAG: groundedness/relevancia...). Consulta los nombres exactos en el paquete instalado (`openevals.prompts`).

### Rúbrica propia
```python
TONE_PROMPT = """Evalúa si la respuesta sigue la guía de tono de soporte.
Criterios (todos obligatorios):
1. Trata al usuario de "tú" y en español neutro.
2. No promete plazos ni compensaciones no confirmadas.
3. Termina con un siguiente paso claro.
<pregunta>{inputs}</pregunta>
<respuesta>{outputs}</respuesta>
Responde true solo si cumple los 3 criterios."""

tone_judge = create_llm_as_judge(prompt=TONE_PROMPT, model=settings.judge_model, feedback_key="tone")
```
Buenas prácticas del juez:
- Criterios binarios o escala corta (1–3); pide razonamiento antes de la nota (openevals lo hace con `comment`).
- Calibra: etiqueta 20–50 ejemplos a mano y mide el acuerdo del juez antes de usarlo para decidir.
- Fija `temperature=0` y versiona el prompt del juez; si cambias el juez, re-ejecuta la línea base.

## 2. Evaluadores deterministas útiles
```python
import json

def valid_json(outputs: dict) -> dict:
    try:
        json.loads(outputs["raw"])
        return {"key": "valid_json", "score": True}
    except (json.JSONDecodeError, KeyError):
        return {"key": "valid_json", "score": False}

def latency_budget(run, example) -> dict:
    secs = (run.end_time - run.start_time).total_seconds()
    return {"key": "under_3s", "score": secs < 3, "comment": f"{secs:.2f}s"}

def cites_expected_source(outputs: dict, reference_outputs: dict) -> dict:
    hit = set(reference_outputs["source_ids"]) & set(outputs.get("source_ids", []))
    return {"key": "source_hit", "score": bool(hit)}
```

## 3. Evaluadores de resumen (sobre todo el experimento)
```python
def f1_summary(outputs: list[dict], reference_outputs: list[dict]) -> dict:
    tp = sum(o["category"] == r["category"] == "billing" for o, r in zip(outputs, reference_outputs))
    fp = sum(o["category"] == "billing" != r["category"] for o, r in zip(outputs, reference_outputs))
    fn = sum(r["category"] == "billing" != o["category"] for o, r in zip(outputs, reference_outputs))
    f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    return {"key": "billing_f1", "score": f1}

client.evaluate(target, data="support-triage-v1", evaluators=[exact_category],
                summary_evaluators=[f1_summary], num_repetitions=3,
                experiment_prefix="triage-v4")
```
`num_repetitions` mide la varianza de salidas no deterministas.

## 4. Agentes: trayectorias con agentevals
```python
from agentevals.trajectory.match import create_trajectory_match_evaluator

trajectory_match = create_trajectory_match_evaluator(trajectory_match_mode="superset")
# modos: "strict", "unordered", "subset", "superset"

async def target(inputs: dict) -> dict:
    result = await agent.ainvoke({"messages": [{"role": "user", "content": inputs["question"]}]})
    return {"messages": result["messages"]}

def tools_used(outputs: dict, reference_outputs: dict):
    return trajectory_match(outputs=outputs["messages"], reference_outputs=reference_outputs["messages"])
```
También existe un juez de trayectorias con LLM (`create_trajectory_llm_as_judge` en `agentevals.trajectory.llm`); verifica firma y prompts en la versión instalada. Evalúa además el resultado final (corrección) y el coste (número de llamadas al modelo/tools).

## 5. Evaluar un grafo LangGraph directamente
```python
from langsmith import aevaluate

async def target(inputs: dict) -> dict:
    out = await graph.ainvoke({"messages": [{"role": "user", "content": inputs["question"]}]},
                              {"configurable": {"thread_id": str(uuid4())}})
    return {"answer": out["messages"][-1].text}

await aevaluate(target, data="support-qa-v1", evaluators=[correctness],
                experiment_prefix="graph-v2", max_concurrency=4)
```
Usa un `thread_id` nuevo por ejemplo para que no se contaminen entre sí. Para evaluar un nodo concreto, invoca la función del nodo con estados de ejemplo.

## 6. Comparar experimentos
- Mismo dataset + misma versión del dataset (`as_of`/tag) + evaluadores idénticos.
- Metadata del experimento: `model`, `prompt_version`, `git_sha`, parámetros (k, chunk_size).
- En la UI compara experimentos lado a lado y filtra regresiones por ejemplo. Evaluación pairwise (A vs B con un juez) para preferencias subjetivas: disponible vía `evaluate` con evaluadores comparativos; verifica la API en la documentación de tu versión.

## 7. Evaluaciones en pytest (y Vitest/Jest)
```python
import pytest
from langsmith import testing as t

@pytest.mark.langsmith
def test_triage_billing():
    ticket = "Me cobraron dos veces"
    t.log_inputs({"ticket": ticket})
    t.log_reference_outputs({"category": "billing"})
    result = triage_chain.invoke(ticket)
    t.log_outputs({"category": result.category})
    t.log_feedback(key="correct", score=result.category == "billing")
    assert result.category == "billing"
```
Ejecución: `LANGSMITH_TEST_SUITE="support-triage" pytest tests/evals --langsmith-output`. `LANGSMITH_TEST_TRACKING=false` para ejecutar sin sincronizar; `LANGSMITH_TEST_CACHE=path` para cachear llamadas HTTP y abaratar re-ejecuciones.
Colócalos en `tests/evals/` y exclúyelos del suite rápido (marker o directorio). El SDK JS ofrece integración análoga para Vitest/Jest (`langsmith/vitest`, `langsmith/jest`); verifica el import en tu versión.

## 8. Prompts
```python
from langsmith import Client
client = Client()

client.push_prompt("support-system", object=ChatPromptTemplate.from_messages([...]))
prompt = client.pull_prompt("support-system:3f2a9c1b")                 # commit
chain = client.pull_prompt("support-triage", include_model=True)       # incluye config de modelo
```
JS: `import * as hub from "langchain/hub"; const prompt = await hub.pull("support-system");`.
- Promociona versiones con tags (`staging`, `prod`) desde la UI tras evaluar.
- Cachea con TTL y conserva un fallback embebido en el código.

## 9. Producción
- **Feedback de usuario** (pulgar arriba/abajo, correcciones) asociado al run:
```python
run_id = ls.uuid7()
await answer_question(q, langsmith_extra={"run_id": run_id})
# ... cuando llega el feedback del cliente:
client.create_feedback(run_id=run_id, key="user_score", score=1, comment="útil")
```
  Devuelve `run_id` al frontend para que el endpoint de feedback lo reenvíe.
- **Filtros guardados** por metadata (tenant, feature), error, latencia y tokens; revisa semanalmente los peores casos.
- **Reglas de automatización / evaluadores online**: evalúan una muestra de trazas de producción (p. ej. groundedness con LLM-as-judge) y pueden enviar trazas a colas de anotación o añadirlas a datasets. Se configuran en la UI del proyecto.
- **Alertas** sobre tasa de error, latencia p95 o feedback negativo.
- **Cerrar el ciclo**: trazas malas → cola de anotación → dataset → experimento → despliegue → monitoreo.
