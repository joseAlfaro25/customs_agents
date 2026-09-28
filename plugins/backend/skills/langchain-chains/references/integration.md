# Middleware, streaming e integración HTTP

Verifica siempre la versión instalada de `langchain`/`langgraph` (Python) o `langchain`/`@langchain/*` (JS) antes de copiar.

## 1. Middleware de create_agent

### Prompt dinámico según el contexto
```python
from langchain.agents.middleware import ModelRequest, dynamic_prompt

@dynamic_prompt
def tenant_prompt(request: ModelRequest) -> str:
    ctx = request.runtime.context          # instancia de context_schema
    return f"Eres el asistente de {ctx.tenant_name}. Responde en {ctx.language}."
```

### Selección dinámica de modelo
```python
from collections.abc import Callable
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call

fast = init_chat_model("anthropic:claude-haiku-4-5")
strong = init_chat_model("anthropic:claude-sonnet-5")

@wrap_model_call
def route_model(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    model = strong if len(request.messages) > 10 else fast
    return handler(request.override(model=model))
```
Para agentes invocados con `ainvoke`/`astream`, define hooks async (`async def` con el mismo decorador, o `awrap_model_call` en una subclase de `AgentMiddleware`); verifica en la documentación de tu versión.

### Guardrail antes del modelo
```python
from langchain.agents.middleware import AgentState, before_model
from langgraph.runtime import Runtime

@before_model(can_jump_to=["end"])
def max_turns(state: AgentState, runtime: Runtime) -> dict | None:
    if len(state["messages"]) > 40:
        return {"messages": [AIMessage("La conversación es demasiado larga, empieza una nueva.")], "jump_to": "end"}
    return None
```

### Human-in-the-loop sobre tools
```python
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.types import Command

agent = create_agent(
    model=model,
    tools=[refund_order, get_order_status],
    middleware=[HumanInTheLoopMiddleware(
        interrupt_on={
            "refund_order": {"allowed_decisions": ["approve", "edit", "reject"]},
            "get_order_status": False,
        },
        description_prefix="Acción pendiente de aprobación",
    )],
    checkpointer=checkpointer,   # obligatorio para interrumpir y reanudar
)

cfg = {"configurable": {"thread_id": thread_id}}
result = await agent.ainvoke({"messages": [{"role": "user", "content": "Reembolsa el pedido 42"}]}, cfg)
if "__interrupt__" in result:
    pending = result["__interrupt__"][0].value      # acciones pendientes y decisiones permitidas
    # ... enviar al cliente, esperar decisión ...
result = await agent.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg)
```
Una decisión por acción pendiente y en el mismo orden. `edit` y `reject` aceptan campos adicionales (argumentos editados, mensaje); consulta el formato exacto en la guía de human-in-the-loop de tu versión.

### Límites y resiliencia
```python
from langchain.agents.middleware import (
    ModelCallLimitMiddleware, ModelFallbackMiddleware, SummarizationMiddleware, ToolCallLimitMiddleware,
)

middleware = [
    SummarizationMiddleware(model=fast, trigger=("tokens", 4000), keep=("messages", 20)),
    ModelCallLimitMiddleware(run_limit=10, exit_behavior="end"),
    ToolCallLimitMiddleware(tool_name="search", run_limit=5),
    ModelFallbackMiddleware(fast),       # modelos alternativos si falla el principal
]
```
Los formatos de `trigger`/`keep` han cambiado entre versiones menores: comprueba la firma en la referencia de la versión instalada.

## 2. FastAPI

### Construcción en lifespan e inyección
```python
# app/llm/agent.py
def build_support_agent(model, checkpointer):
    return create_agent(model=model, tools=[get_order_status], context_schema=Context,
                        system_prompt=SUPPORT_PROMPT, checkpointer=checkpointer)

# app/main.py
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    model = init_chat_model(s.llm_model, temperature=0, timeout=30, max_retries=2)
    async with AsyncPostgresSaver.from_conn_string(s.checkpoint_db_url) as checkpointer:
        await checkpointer.setup()       # idempotente; también puede ir en una migración
        app.state.support_agent = build_support_agent(model, checkpointer)
        yield

# app/llm/deps.py
def get_support_agent(request: Request):
    return request.app.state.support_agent

AgentDep = Annotated[CompiledStateGraph, Depends(get_support_agent)]
```
`checkpoint_db_url` usa formato psycopg (`postgresql://...`), no `postgresql+asyncpg://`.

### Endpoint JSON
```python
class ChatIn(BaseModel):
    thread_id: UUID
    message: str = Field(min_length=1, max_length=4000)

class ChatOut(BaseModel):
    answer: str

@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn, agent: AgentDep, user: CurrentUser) -> ChatOut:
    await ensure_thread_owner(body.thread_id, user.id)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": body.message}]},
        config={"configurable": {"thread_id": str(body.thread_id)},
                "run_name": "support_chat", "metadata": {"user_id": str(user.id)}},
        context=Context(user_id=str(user.id)),
    )
    return ChatOut(answer=result["messages"][-1].text)
```

### Endpoint SSE
```python
import json
from fastapi.responses import StreamingResponse

@router.post("/chat/stream")
async def chat_stream(body: ChatIn, request: Request, agent: AgentDep, user: CurrentUser):
    await ensure_thread_owner(body.thread_id, user.id)

    async def events():
        try:
            async for chunk in agent.astream(
                {"messages": [{"role": "user", "content": body.message}]},
                config={"configurable": {"thread_id": str(body.thread_id)}},
                context=Context(user_id=str(user.id)),
                stream_mode=["messages", "updates"],
                version="v2",
            ):
                if await request.is_disconnected():
                    break
                if chunk["type"] == "messages":
                    token, meta = chunk["data"]
                    if token.text and meta.get("langgraph_node") == "model":
                        yield f"event: token\ndata: {json.dumps({'text': token.text})}\n\n"
                elif chunk["type"] == "updates" and "__interrupt__" in chunk["data"]:
                    yield f"event: interrupt\ndata: {json.dumps({'pending': True})}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception:
            logger.exception("stream failed")
            yield "event: error\ndata: {\"detail\": \"stream failed\"}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```
El nombre del nodo del modelo en `create_agent` es `"model"` en 1.x; confírmalo inspeccionando `meta["langgraph_node"]` en tu versión.

### Cadena LCEL simple
```python
def get_summary_chain(request: Request):
    return request.app.state.summary_chain       # prompt | model | StrOutputParser()

@router.post("/summaries")
async def summarize(body: SummaryIn, chain: Annotated[Runnable, Depends(get_summary_chain)]):
    text = await chain.ainvoke({"text": body.text, "language": "es", "max_words": 80},
                               config={"run_name": "summarize"})
    return {"summary": text}
```

## 3. NestJS (LangChain.js)

### Provider del agente
```ts
// src/llm/llm.module.ts
export const SUPPORT_AGENT = Symbol('SUPPORT_AGENT');

@Module({
  providers: [
    {
      provide: SUPPORT_AGENT,
      inject: [ConfigService, OrdersService],
      useFactory: async (config: ConfigService, orders: OrdersService) => {
        const model = await initChatModel(config.getOrThrow('LLM_MODEL'), { temperature: 0, timeout: 30_000 });
        const checkpointer = PostgresSaver.fromConnString(config.getOrThrow('CHECKPOINT_DB_URL'));
        await checkpointer.setup();
        return createAgent({
          model,
          tools: [makeOrderStatusTool(orders)],
          systemPrompt: SUPPORT_PROMPT,
          checkpointer,
        });
      },
    },
  ],
  exports: [SUPPORT_AGENT],
})
export class LlmModule {}
```
`PostgresSaver` viene de `@langchain/langgraph-checkpoint-postgres`; verifica el nombre del export en la versión instalada.

### Controller JSON y SSE
```ts
@Controller({ path: 'chat', version: '1' })
export class ChatController {
  constructor(@Inject(SUPPORT_AGENT) private readonly agent: ReturnType<typeof createAgent>) {}

  @Post()
  async chat(@Body() dto: ChatDto) {
    const result = await this.agent.invoke(
      { messages: [{ role: 'user', content: dto.message }] },
      { configurable: { thread_id: dto.threadId }, runName: 'support_chat' },
    );
    return { answer: result.messages.at(-1)?.text };
  }

  @Post('stream')
  async stream(@Body() dto: ChatDto, @Res() res: Response) {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    const stream = await this.agent.stream(
      { messages: [{ role: 'user', content: dto.message }] },
      { configurable: { thread_id: dto.threadId }, streamMode: 'messages' },
    );
    for await (const [token] of stream) {
      if (token.text) res.write(`event: token\ndata: ${JSON.stringify({ text: token.text })}\n\n`);
    }
    res.write('event: done\ndata: {}\n\n');
    res.end();
  }
}
```
Alternativa idiomática para GET: `@Sse('stream')` devolviendo `Observable<MessageEvent>` (`from(asyncIterable).pipe(map(...))`). `@Sse` solo admite GET; para POST usa `@Res()` como arriba.

### Tool con dependencias de Nest
```ts
export const makeOrderStatusTool = (orders: OrdersService) =>
  tool(async ({ orderId }, config) => {
    const userId = config?.configurable?.user_id;
    const order = await orders.findForUser(orderId, userId);
    return order ? `Pedido ${orderId}: ${order.status}` : 'Pedido no encontrado';
  }, {
    name: 'get_order_status',
    description: 'Devuelve el estado de un pedido del usuario actual',
    schema: z.object({ orderId: z.string() }),
  });
```
En LangChain.js 1.x también existe `contextSchema` + `runtime.context` en `createAgent`; prefierelo a `configurable` para datos del usuario si tu versión lo soporta.
