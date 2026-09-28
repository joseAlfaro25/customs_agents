# Fixtures de DB y testing de código LLM

## 1. pytest + Postgres (Testcontainers) + rollback por test

```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer
from app.core.db import Base

@pytest.fixture(scope="session")
def pg_url():
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as pg:
        yield pg.get_connection_url()      # postgresql+asyncpg://...

@pytest.fixture(scope="session")
async def engine(pg_url):
    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)   # o ejecuta alembic upgrade head
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(engine):
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False,
                               join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
```
- `join_transaction_mode="create_savepoint"` permite que el código bajo test haga `commit()` sin romper el rollback exterior (SQLAlchemy 2.x).
- Fixtures async con `scope="session"` requieren que el loop también sea de sesión: en pytest-asyncio configura `asyncio_default_fixture_loop_scope = "session"` o marca los tests con `@pytest.mark.asyncio(loop_scope="session")`. Verifica la versión instalada; con anyio usa un fixture `anyio_backend` de sesión.
- Si el proyecto ya tiene Postgres en `docker compose`, usa `DATABASE_URL` de test en lugar de Testcontainers.

### Ejecutar migraciones reales en la fixture
```python
from alembic import command
from alembic.config import Config

def run_migrations(sync_url: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")
```
Con `env.py` async, `command.upgrade` funciona igual (el propio env.py gestiona el loop); llámalo desde una fixture sync o con `await asyncio.to_thread(...)`.

### App con lifespan
```python
from asgi_lifespan import LifespanManager

@pytest.fixture
async def client(app):
    async with LifespanManager(app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as c:
            yield c
```

### Auth override
```python
@pytest.fixture
def as_user(app):
    user = User(id=uuid4(), roles=["user"])
    app.dependency_overrides[get_current_user] = lambda: user
    return user
```

## 2. NestJS e2e con DB real

```ts
// test/setup-db.ts (Testcontainers)
import { PostgreSqlContainer, StartedPostgreSqlContainer } from '@testcontainers/postgresql';

let container: StartedPostgreSqlContainer;

export async function startDb() {
  container = await new PostgreSqlContainer('postgres:17-alpine').start();
  process.env.DATABASE_URL = container.getConnectionUri();
  return container;
}
export const stopDb = () => container?.stop();
```
```ts
beforeAll(async () => {
  await startDb();
  const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
  app = moduleRef.createNestApplication();
  configureApp(app);
  await app.init();
  const ds = app.get(DataSource);
  await ds.runMigrations();          // TypeORM; con Prisma: execSync('npx prisma migrate deploy')
}, 60_000);

afterEach(async () => {
  const ds = app.get(DataSource);
  await ds.query('TRUNCATE orders, customers RESTART IDENTITY CASCADE');
});

afterAll(async () => { await app.close(); await stopDb(); });
```
- Usa `--runInBand` en e2e para evitar colisiones sobre la misma DB, o una DB/esquema por worker (`JEST_WORKER_ID`).
- Nombres de import de Testcontainers cambian entre versiones mayores (`PostgreSqlContainer`); verifica en `package.json`.

## 3. Testing de código LLM

### Fake chat model con soporte de tools (Python)
```python
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain.messages import AIMessage, ToolCall

class FakeToolModel(GenericFakeChatModel):
    """GenericFakeChatModel no implementa bind_tools; create_agent lo necesita."""
    def bind_tools(self, tools, **kwargs):
        return self

def make_model(*responses):
    return FakeToolModel(messages=iter(responses))

def test_agent_calls_weather_tool():
    model = make_model(
        AIMessage(content="", tool_calls=[ToolCall(name="get_weather", args={"city": "Lima"}, id="call_1")]),
        AIMessage(content="En Lima hace 20 grados."),
    )
    agent = create_agent(model, tools=[get_weather])
    result = agent.invoke({"messages": [{"role": "user", "content": "¿Clima en Lima?"}]})
    tool_msgs = [m for m in result["messages"] if m.type == "tool"]
    assert tool_msgs and "Lima" in tool_msgs[0].content
    assert result["messages"][-1].content == "En Lima hace 20 grados."
```
- El iterador se consume una respuesta por llamada al modelo: prepara exactamente las necesarias.
- Si usas `response_format`, el fake debe devolver la tool call de la estrategia (ToolStrategy) o el JSON esperado; suele ser más simple testear el parser/schema por separado.

### Cadenas LCEL
```python
def test_summary_chain_uses_prompt():
    model = GenericFakeChatModel(messages=iter(["resumen"]))
    chain = build_summary_chain(model)          # la factory recibe el modelo inyectado
    assert chain.invoke({"text": "largo..."}) == "resumen"
```
Diseña factories que reciban el modelo (`build_chain(model)`) para poder inyectar el fake.

### Structured output sin LLM
Testea el schema Pydantic y los validadores con dicts de ejemplo, y el manejo de `ValidationError`/salida malformada con un fake que devuelva JSON inválido.

### Grafos LangGraph
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

def test_route_node():
    assert route({"messages": [], "needs_approval": True}) == "approval"

async def test_graph_interrupt_and_resume():
    graph = build_graph(model=make_model(...), checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "t1"}}
    out = await graph.ainvoke({"messages": [{"role": "user", "content": "borra X"}]}, cfg)
    assert "__interrupt__" in out
    out = await graph.ainvoke(Command(resume={"approved": False}), cfg)
    assert out["status"] == "cancelled"
```
- Nodos individuales: llama a la función del nodo con un estado construido a mano y verifica la actualización devuelta.
- Usa `graph.get_state(cfg)` para verificar el estado persistido y `next` pendiente.

### Endpoints con LLM
FastAPI: `app.dependency_overrides[get_agent] = lambda: fake_agent`. Nest: `.overrideProvider(LLM_AGENT).useValue(fakeAgent)`. Para SSE, lee el body completo y verifica los eventos `data: ...`.

### JS/TS
```ts
import { FakeListChatModel } from '@langchain/core/utils/testing';
const model = new FakeListChatModel({ responses: ['respuesta 1', 'respuesta 2'] });
```
Para agentes con tools en JS, verifica en la versión instalada de `@langchain/core` qué fake soporta `bindTools`; alternativa: mockear el provider completo del agente.

### Evaluaciones (fuera del suite unitario)
- pytest con `@pytest.mark.langsmith` y `langsmith.testing` para registrar inputs/outputs/feedback.
- Job separado en CI (nightly o por label) con claves reales y umbrales de métricas. Ver `backend:langsmith-observability`.
