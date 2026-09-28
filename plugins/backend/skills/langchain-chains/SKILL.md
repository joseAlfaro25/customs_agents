---
name: langchain-chains
description: "Patrones de LangChain 1.x: chat models (init_chat_model), mensajes, prompts, LCEL y runnables, structured output, tools, create_agent con middleware, streaming e integración en endpoints FastAPI y NestJS (LangChain.js). Usar al añadir llamadas a LLMs, cadenas, tools o agentes simples a un backend."
---

# langchain-chains

## Objetivo
Integrar LLMs en backends con LangChain 1.x de forma tipada, testeable y observable: elegir la primitiva mínima (modelo → structured output → LCEL → `create_agent`), inyectar el modelo como dependencia y exponerlo por HTTP con o sin streaming.

## Cuándo aplicarla
- Llamar a un modelo para clasificar, extraer, resumir o generar.
- Obtener salida estructurada validada.
- Definir tools y un agente con `create_agent` (+ middleware).
- Exponer la funcionalidad en FastAPI o NestJS, incluyendo streaming SSE.
- Migrar código 0.x (`LLMChain`, `initialize_agent`, `ConversationChain`).

## Antes de empezar
1. Carga `core:project-context`. **Verifica la versión en el manifiesto del proyecto**: esta skill apunta a `langchain` 1.x (1.4 en sept. 2026), `langchain-core` 1.x, `langgraph` 1.x y paquetes de proveedor (`langchain-anthropic`, `langchain-openai`, `langchain-google-genai`...). En JS: `langchain` 1.x, `@langchain/core`, `@langchain/langgraph`, `@langchain/anthropic`/`@langchain/openai`.
2. Cambios clave 0.x → 1.x: `create_agent` (en `langchain.agents`) sustituye a `initialize_agent`/`AgentExecutor` y a `langgraph.prebuilt.create_react_agent`; middleware reemplaza hooks ad hoc; mensajes exponen `content_blocks` estándar; `.text` es propiedad; las chains legacy (`LLMChain`, `RetrievalQA`...) viven en `langchain-classic`.
3. Si una firma no aparece aquí o dudas, verifica en `docs.langchain.com/oss/python/langchain/` antes de escribirla.

Instalación típica: `uv add langchain langchain-anthropic` (o `"langchain[anthropic]"`); JS: `npm i langchain @langchain/core @langchain/anthropic`.

## Modelos de chat
```python
from langchain.chat_models import init_chat_model

model = init_chat_model(
    settings.llm_model,            # "anthropic:claude-sonnet-5", "openai:gpt-5.5"...
    temperature=0,
    timeout=30,
    max_retries=2,
)
resp = await model.ainvoke([
    {"role": "system", "content": "Eres un clasificador de tickets."},
    {"role": "user", "content": ticket_text},
])
resp.text            # texto plano
resp.content_blocks  # bloques estándar (text, reasoning, tool_call, ...)
resp.usage_metadata  # tokens
```
- El id del modelo va en settings/env (`LLM_MODEL`); no lo hardcodees por el código. Revisa la documentación del proveedor para el id vigente.
- Clases de proveedor (`ChatAnthropic`, `ChatOpenAI`) cuando necesites parámetros específicos.
- Métodos: `invoke/ainvoke`, `stream/astream`, `batch/abatch` (con `config={"max_concurrency": n}`).

## Prompts
```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "Resume el texto en {language}. Máximo {max_words} palabras."),
    MessagesPlaceholder("history", optional=True),
    ("human", "{text}"),
])
```
- Datos del usuario solo en mensajes `human`/variables, nunca concatenados en instrucciones del system.
- Prompts de producción: versiónalos en LangSmith y cárgalos por tag/commit (`backend:langsmith-observability`).

## LCEL y runnables
```python
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough

summary_chain = prompt | model | StrOutputParser()

analysis = RunnableParallel(
    summary=summary_chain,
    sentiment=sentiment_prompt | model.with_structured_output(Sentiment),
    original=RunnablePassthrough(),
)
result = await analysis.ainvoke({"text": text, "language": "es", "max_words": 80})
```
- Todo runnable soporta `invoke/ainvoke/stream/astream/batch` y `config` (`run_name`, `tags`, `metadata`, `callbacks`).
- `.with_retry(stop_after_attempt=3)`, `.with_fallbacks([otro_modelo])`, `.with_config(run_name="summarize")`.
- Usa LCEL para pipelines deterministas; si hay bucles o decisiones del modelo, usa `create_agent` o LangGraph.

## Structured output
```python
from pydantic import BaseModel, Field

class TicketTriage(BaseModel):
    category: Literal["billing", "bug", "feature", "other"] = Field(description="Categoría principal")
    priority: int = Field(ge=1, le=4, description="1 = urgente")
    summary: str = Field(description="Resumen en una frase")

triage = model.with_structured_output(TicketTriage)     # method: "json_schema" | "function_calling" | "json_mode"
result: TicketTriage = await triage.ainvoke(ticket_text)
```
- `include_raw=True` devuelve `{"raw", "parsed", "parsing_error"}` para manejar fallos sin excepción.
- `Field(description=...)` en cada campo: el modelo lo usa como instrucción.

## Tools
```python
from langchain.tools import tool, ToolRuntime

@tool
async def get_order_status(order_id: str, runtime: ToolRuntime[Context]) -> str:
    """Devuelve el estado de un pedido del usuario actual. Usa el ID exacto del pedido."""
    order = await orders_repo.get_for_user(order_id, user_id=runtime.context.user_id)
    return f"Pedido {order_id}: {order.status}" if order else "Pedido no encontrado"
```
- Type hints obligatorios (definen el schema); docstring = descripción para el modelo; `args_schema=` para inputs complejos.
- `ToolRuntime` da acceso a `state`, `context`, `store`, `stream_writer` y `tool_call_id` sin exponerlos al modelo.
- Autorización dentro de la tool usando el contexto del usuario autenticado, nunca un ID que el modelo invente.
- Devuelve errores como texto útil para que el modelo se recupere; excepciones solo para fallos irrecuperables.

## Agentes con create_agent
```python
from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, SummarizationMiddleware

@dataclass
class Context:
    user_id: str

agent = create_agent(
    model=model,
    tools=[get_order_status],
    system_prompt="Eres el asistente de soporte. Responde en español y cita el ID del pedido.",
    context_schema=Context,
    middleware=[ModelCallLimitMiddleware(run_limit=8)],
    response_format=None,          # o un schema Pydantic → result["structured_response"]
    checkpointer=checkpointer,     # multi-turno: requiere thread_id en config
)
result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": question}]},
    config={"configurable": {"thread_id": thread_id}, "metadata": {"user_id": user.id}},
    context=Context(user_id=user.id),
)
answer = result["messages"][-1].text
```
Middleware integrado (`langchain.agents.middleware`): `SummarizationMiddleware`, `HumanInTheLoopMiddleware(interrupt_on={...})`, `ModelCallLimitMiddleware`, `ToolCallLimitMiddleware`, `ModelFallbackMiddleware`, `ModelRetryMiddleware`, `ToolRetryMiddleware`, `PIIMiddleware`. Custom: decoradores `@before_model`, `@after_model`, `@wrap_model_call`, `@wrap_tool_call`, `@dynamic_prompt` o subclase de `AgentMiddleware`. Structured output en agentes: `response_format=Schema` (elige `ProviderStrategy` si el proveedor lo soporta, si no `ToolStrategy`), importables de `langchain.agents.structured_output`.

Ejemplos de middleware, streaming e integración completa en FastAPI y NestJS: lee [references/integration.md](references/integration.md) cuando vayas a exponer una cadena o agente por HTTP o a escribir middleware propio.

## Streaming
- Modelo o cadena: `async for chunk in chain.astream(inputs): chunk.text` (o el string si termina en `StrOutputParser`).
- Agente/grafo: `agent.astream(inputs, stream_mode="messages", version="v2")` produce `{"type": "messages", "data": (token, metadata)}`; combina modos con `stream_mode=["updates", "messages", "custom"]`. `version="v2"` requiere LangGraph ≥ 1.1.
- LangChain ≥ 1.3 / LangGraph ≥ 1.2 añaden `stream_events(version="v3")` con proyecciones tipadas (`.messages`, `.values`, `.output`, `.interrupts`); está en **beta**: úsalo solo si el proyecto ya lo adopta y verifica la API.

## Equivalentes JS/TS (NestJS)
```ts
import { createAgent, initChatModel, tool } from 'langchain';
import * as z from 'zod';

const model = await initChatModel(config.getOrThrow('LLM_MODEL'), { temperature: 0 });
const triage = model.withStructuredOutput(z.object({ category: z.enum(['billing', 'bug', 'other']) }));

const getOrderStatus = tool(async ({ orderId }) => `...`, {
  name: 'get_order_status',
  description: 'Devuelve el estado de un pedido',
  schema: z.object({ orderId: z.string() }),
});
const agent = createAgent({ model, tools: [getOrderStatus], systemPrompt: '...' });
```
Prompts y LCEL en `@langchain/core/prompts` y `@langchain/core/runnables` (`.pipe()` en lugar de `|`).

## Antipatrones
- `invoke` sync dentro de `async def`; crear el modelo/agente en cada request.
- Parsear JSON del texto con regex en vez de `with_structured_output`.
- Tools que confían en IDs de usuario generados por el modelo; tools destructivas sin HITL.
- Mezclar APIs 0.x (`LLMChain`, `initialize_agent`, `AgentExecutor`) con 1.x en código nuevo.
- Sin `timeout`/`max_retries`; sin límite de iteraciones en agentes.
- Prompts con PII registrados en logs.

## Checklist final
- [ ] Versiones verificadas; imports 1.x consistentes.
- [ ] Modelo configurado desde settings con `timeout` y `max_retries`.
- [ ] Salidas estructuradas con Pydantic/Zod cuando el consumidor es código.
- [ ] Tools tipadas, con docstring y autorización por contexto.
- [ ] Agente con límites (llamadas/tools) y checkpointer si es multi-turno.
- [ ] Endpoint async con streaming si la respuesta es larga; desconexión manejada.
- [ ] `run_name`/`tags`/`metadata` para LangSmith.
- [ ] Tests con modelo fake (`backend:backend-testing`); lint y typecheck en verde.
