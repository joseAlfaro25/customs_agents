# Guía rápida: LangChain y LangGraph

Guía agnóstica al proyecto para arrancar con LangChain y LangGraph en Python.

## 1. Qué es cada una y cuándo usarla

**LangChain** es la capa de *componentes*: una interfaz común para modelos de chat, prompts, parsers, tools y retrievers. Te permite cambiar de proveedor (OpenAI, Azure, Anthropic, Bedrock…) sin reescribir la lógica.

**LangGraph** es la capa de *orquestación*: modela tu aplicación como un grafo de estado (nodos + transiciones) con persistencia, reintentos, interrupciones humanas y streaming. Usa los componentes de LangChain por dentro, pero no depende de ellos.

| Necesitas… | Usa |
|---|---|
| Una llamada al LLM, extracción, clasificación, resumen | LangChain (modelo + prompt + structured output) |
| Un agente simple que decide qué tool llamar | `create_agent` de LangChain (ya corre sobre LangGraph) |
| Flujo con pasos fijos, ramas, bucles o varios agentes | LangGraph `StateGraph` |
| Conversación con memoria entre turnos o aprobación humana | LangGraph + checkpointer |

Regla práctica: empieza con lo más simple que funcione; pasa a un grafo propio cuando necesites controlar *explícitamente* el orden de los pasos o el estado.

## 2. Instalación y configuración mínima

```bash
pip install -U langchain langgraph langsmith
# + el paquete del proveedor que uses (uno por proveedor):
pip install -U langchain-openai      # OpenAI / Azure OpenAI
pip install -U langchain-anthropic   # Anthropic
# Persistencia en producción (opcional):
pip install -U langgraph-checkpoint-postgres
```

Variables de entorno típicas (nunca en el código; cárgalas con `pydantic-settings` o `.env`):

```bash
OPENAI_API_KEY=...            # o AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=mi-proyecto-dev
```

Fija versiones en `requirements.txt`/`pyproject.toml`: el ecosistema cambia rápido y los cambios de API entre versiones menores son frecuentes.

## 3. LangChain: los 4 bloques básicos

**Modelo** — una sola función para cualquier proveedor:

```python
from langchain.chat_models import init_chat_model

llm = init_chat_model("openai:gpt-4.1-mini", temperature=0)
llm.invoke("Hola")            # -> AIMessage
```

**Prompt** — plantillas con variables; separa instrucciones (system) de la entrada del usuario:

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "Eres un asistente de {dominio}. Responde en español."),
    ("placeholder", "{messages}"),   # historial de la conversación
])
chain = prompt | llm                  # LCEL: compone con |
chain.invoke({"dominio": "ventas", "messages": [("user", "¿Qué ofreces?")]})
```

**Structured output** — la forma más fiable de obtener datos, no texto:

```python
from pydantic import BaseModel, Field

class Intencion(BaseModel):
    categoria: str = Field(description="agendar | preguntar | otro")
    confianza: float

clasificador = prompt | llm.with_structured_output(Intencion)
resultado = clasificador.invoke({...})   # -> Intencion
```

**Tools** — funciones que el modelo puede decidir llamar. El docstring y los type hints son lo que el modelo lee:

```python
from langchain_core.tools import tool

@tool
def consultar_disponibilidad(fecha: str) -> list[str]:
    """Devuelve las horas libres para una fecha YYYY-MM-DD."""
    return repo.horas_libres(fecha)

llm_con_tools = llm.bind_tools([consultar_disponibilidad])
```

Todos estos objetos son `Runnable`: comparten `invoke`, `ainvoke`, `batch`, `stream` y `with_retry()`/`with_fallbacks()`.

## 4. LangGraph: estado, nodos y edges

Un grafo tiene tres piezas:

1. **Estado** — un `TypedDict` (o Pydantic) que viaja por todo el grafo. Cada campo puede tener un *reducer* que define cómo se combinan las actualizaciones (p. ej. `add_messages` acumula mensajes en vez de sobrescribirlos).
2. **Nodos** — funciones `estado -> dict parcial`. Solo devuelven los campos que cambian.
3. **Edges** — transiciones fijas (`add_edge`) o condicionales (`add_conditional_edges`, una función que elige el siguiente nodo).

```python
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]
    intencion: str | None

def clasificar(state: State) -> dict:
    r = clasificador.invoke({"messages": state["messages"]})
    return {"intencion": r.categoria}

def agendar(state: State) -> dict:
    return {"messages": [agente_agenda.invoke(state["messages"])]}

def responder(state: State) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}

def enrutar(state: State) -> str:
    return "agendar" if state["intencion"] == "agendar" else "responder"

builder = StateGraph(State)
builder.add_node("clasificar", clasificar)
builder.add_node("agendar", agendar)
builder.add_node("responder", responder)
builder.add_edge(START, "clasificar")
builder.add_conditional_edges("clasificar", enrutar, ["agendar", "responder"])
builder.add_edge("agendar", END)
builder.add_edge("responder", END)

graph = builder.compile()
graph.invoke({"messages": [("user", "Quiero una cita el martes")]})
```

Alternativa a los edges condicionales: un nodo puede devolver `Command(goto="otro_nodo", update={...})` para decidir el salto y actualizar el estado a la vez. Útil en routers y supervisores.

Para ver el grafo: `graph.get_graph().draw_mermaid()`.

## 5. Memoria y persistencia

Sin checkpointer, cada `invoke` empieza de cero. Con checkpointer, LangGraph guarda el estado después de cada paso, indexado por `thread_id` (una conversación = un thread).

```python
from langgraph.checkpoint.memory import InMemorySaver          # dev / tests
# from langgraph.checkpoint.postgres import PostgresSaver      # producción

graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "usuario-123"}}
graph.invoke({"messages": [("user", "Hola")]}, config)
graph.invoke({"messages": [("user", "¿Qué te dije antes?")]}, config)  # recuerda

graph.get_state(config)   # inspeccionar el estado actual del thread
```

Reglas:

- Elige un `thread_id` estable y con significado de negocio (p. ej. `"<telefono>-<id_entidad>"`): facilita buscar trazas y depurar.
- `InMemorySaver` se pierde al reiniciar; en producción usa Postgres/Redis y llama a `setup()` una vez para crear las tablas.
- El historial crece sin límite: recorta o resume mensajes (`trim_messages` o un nodo de resumen) antes de llamar al modelo.
- Memoria *entre* threads (preferencias del usuario, hechos) va en un `Store`, no en el checkpointer.

## 6. Patrones reutilizables

**Agente con tools (ReAct)** — el modelo decide qué tool llamar hasta tener la respuesta. No lo construyas a mano:

```python
from langchain.agents import create_agent

agente = create_agent(
    model="openai:gpt-4.1-mini",
    tools=[consultar_disponibilidad, reservar_cita],
    system_prompt="Eres el agente de agenda. Solo agendas citas.",
)
agente.invoke({"messages": [("user", "¿Tienes hueco el martes?")]})
```

**Router / supervisor multi-agente** — un nodo clasifica y delega en agentes especializados (cada uno con su prompt y sus tools). Buenas prácticas:

- El router devuelve structured output con un `Literal` de destinos válidos, no texto libre.
- Cada subagente debe tener una salida definida para "no puedo resolver esto" que devuelva el control al router con un motivo, en vez de quedarse sin salida.
- Pon un tope de pasos (`recursion_limit` en el config, por defecto 25) y trata `GraphRecursionError` como un bug: casi siempre son dos nodos rebotándose la conversación.

**Human-in-the-loop** — pausar el grafo para que una persona apruebe o corrija (requiere checkpointer):

```python
from langgraph.types import interrupt, Command

def confirmar(state: State) -> dict:
    decision = interrupt({"pregunta": "¿Confirmas la cita?", "cita": state["cita"]})
    return {"confirmada": decision == "si"}

# Primera llamada: se detiene en interrupt() y devuelve __interrupt__
graph.invoke(entrada, config)
# Cuando la persona responde, se reanuda en el mismo punto:
graph.invoke(Command(resume="si"), config)
```

**Streaming** — `graph.stream(entrada, config, stream_mode="updates")` emite lo que cambia cada nodo; `stream_mode="messages"` emite tokens del LLM para UIs de chat.

## 7. Observabilidad, evaluación y testing

**Tracing (LangSmith)** — con `LANGSMITH_TRACING=true` cada ejecución del grafo queda trazada automáticamente. Añade contexto para poder buscar después:

```python
graph.invoke(entrada, {
    "configurable": {"thread_id": tid},
    "metadata": {"pais": "CO", "canal": "whatsapp"},
    "tags": ["prod"],
    "run_name": "conversacion",
})
```

Para código propio fuera de LangChain, usa `@traceable` de `langsmith`.

**Evaluación** — un cambio de prompt es un cambio de comportamiento. Antes de mergearlo:

1. Mantén un dataset en LangSmith con casos reales (entrada + salida esperada), incluidos los casos borde que ya fallaron.
2. Ejecuta `evaluate()` con evaluadores deterministas (ruta elegida, campos extraídos) y LLM-as-judge solo para lo subjetivo.
3. Compara experimento base vs. cambio (A/B). Reproducir un par de mensajes a mano no sustituye a la suite.

**Tests unitarios** — sin red y deterministas, con modelos fake:

```python
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

def test_responder():
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))
    graph = construir_grafo(llm=fake)          # inyecta el modelo
    out = graph.invoke({"messages": [("user", "hola")]})
    assert out["messages"][-1].content == "ok"
```

Prueba nodos y funciones de enrutamiento como funciones puras (reciben un estado, devuelven un dict), y tools por separado del modelo.

## 8. Checklist y errores comunes

**Estructura sugerida del módulo**

```
agents/
  state.py        # State y reducers
  nodes/          # un archivo por nodo o subagente
  tools/          # @tool, sin lógica de prompt
  prompts/        # o prompts versionados en LangSmith Hub
  graph.py        # build_graph(llm, checkpointer) -> CompiledGraph
tests/
```

**Antes de producción**

- [ ] El modelo y el checkpointer se inyectan en `build_graph(...)` (permite fakes en tests y cambiar proveedor).
- [ ] Salidas que alimentan lógica usan `with_structured_output`, no parsing de texto.
- [ ] Cada tool valida entradas y devuelve errores legibles para el modelo en vez de lanzar excepciones sin capturar.
- [ ] Timeouts y `with_retry()` en llamadas al LLM y a APIs externas; `with_fallbacks()` a un segundo modelo si aplica.
- [ ] `recursion_limit` explícito y alertas sobre `GraphRecursionError`.
- [ ] Checkpointer persistente y `thread_id` estable.
- [ ] Tracing con metadata suficiente para encontrar una conversación concreta.
- [ ] Dataset de evaluación y comparación A/B para cada cambio de prompt.
- [ ] Nada de secretos ni PII innecesaria en prompts o metadata de trazas.

**Errores comunes**

| Síntoma | Causa típica |
|---|---|
| Bucle hasta `GraphRecursionError` | Dos nodos se devuelven el control sin condición de salida |
| El agente "olvida" la conversación | Falta checkpointer o el `thread_id` cambia entre llamadas |
| Mensajes duplicados o perdidos | Campo de lista sin reducer (`add_messages`) o nodo que devuelve el estado entero |
| Texto interno filtrado al usuario | Un flag o mensaje de control del prompt llega sin traducir a la respuesta final |
| Un cambio de prompt rompe otro flujo | Se validó a mano en lugar de con la suite de evaluación |
| Al replicar un agente (otro país/cliente) aparecen bugs ya resueltos | Se copió el prompt base sin los casos borde; extrae la parte común y versiona las diferencias |
