---
name: fastapi-endpoint
description: "Convenciones para endpoints FastAPI: estructura routers/schemas/services/deps, Pydantic v2, Depends con Annotated, async correcto, response_model, status codes, HTTPException y handlers, pydantic-settings y lifespan. Usar al crear o modificar endpoints, dependencias o configuración en FastAPI."
---

# fastapi-endpoint

## Objetivo
Construir endpoints FastAPI correctos y mantenibles: contrato explícito con Pydantic v2, dependencias reutilizables, lógica en servicios, async sin bloqueos, errores consistentes y recursos compartidos gestionados en `lifespan`.

## Cuándo aplicarla
- Crear un router nuevo o añadir endpoints.
- Definir schemas, dependencias (DB, auth, paginación) o exception handlers.
- Configurar settings, `lifespan`, middlewares o CORS.
- Migrar código de Pydantic v1 o de `@app.on_event("startup")`.

## Antes de empezar
1. Carga `core:project-context`; lee `pyproject.toml` y el punto de entrada (`app/main.py`).
2. **Verifica la versión en el manifiesto del proyecto**: esta skill apunta a FastAPI ≥ 0.115, Pydantic 2.x, pydantic-settings 2.x, SQLAlchemy 2.x y Python ≥ 3.11. Si el proyecto usa Pydantic 1.x, no mezcles estilos: sigue el existente o planifica la migración.
3. Detecta la organización actual (por capas o por feature) y respétala.

## Estructura de carpetas
Por feature (recomendada en proyectos medianos/grandes):
```
app/
├── main.py                 # create_app(), lifespan, include_router, handlers
├── core/
│   ├── config.py           # Settings (pydantic-settings)
│   ├── db.py               # engine, async_sessionmaker, get_session
│   ├── errors.py           # excepciones de dominio + handlers
│   └── security.py         # auth deps
├── orders/
│   ├── router.py           # APIRouter
│   ├── schemas.py          # Pydantic: OrderCreate, OrderUpdate, OrderRead, OrderPage
│   ├── service.py          # lógica de negocio
│   ├── repository.py       # consultas SQLAlchemy (opcional)
│   ├── models.py           # modelos ORM
│   └── deps.py             # dependencias específicas (get_order_or_404, ...)
tests/
└── orders/test_router.py
```
Por capas (`app/routers/`, `app/schemas/`, `app/services/`, `app/models/`) también es válida; lo importante es la separación router → service → repository.

## Pasos
1. **Schemas** (`schemas.py`) con Pydantic v2.
2. **Service** async con lógica y excepciones de dominio.
3. **Dependencias** tipadas con `Annotated`.
4. **Router** con `response_model`, `status_code`, `responses` documentadas.
5. **Handlers** de excepciones de dominio registrados en `create_app()`.
6. **Registrar** con `app.include_router(router, prefix="/api/v1")`.
7. **Tests** con `httpx.AsyncClient` (ver `backend:backend-testing`).
8. **Verificar**: `ruff check . && ruff format --check . && pytest`.

Ejemplo completo (settings, db, lifespan, errores RFC 9457, router CRUD con paginación por cursor): lee [references/router-example.md](references/router-example.md) al generar un router desde cero.

## Schemas con Pydantic v2
```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class OrderBase(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount_cents: int = Field(gt=0, description="Importe en centavos")

class OrderCreate(OrderBase):
    customer_id: UUID

class OrderUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("description")
    @classmethod
    def strip(cls, v: str | None) -> str | None:
        return v.strip() if v else v

class OrderRead(OrderBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    customer_id: UUID
    status: str
    created_at: datetime
```
- `model_dump(exclude_unset=True)` para PATCH; `model_validate(obj)` para convertir desde ORM.
- `model_config = ConfigDict(extra="forbid")` en inputs si quieres rechazar campos desconocidos.
- Tabla de migración v1 → v2: `.dict()`→`.model_dump()`, `.parse_obj()`→`.model_validate()`, `orm_mode`→`from_attributes`, `@validator`→`@field_validator`, `@root_validator`→`@model_validator`, `Config`→`model_config`.

## Dependencias con Annotated
```python
from typing import Annotated
from fastapi import Depends, Query

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CurrentUser = Annotated[User, Depends(get_current_user)]

class PageParams(BaseModel):
    limit: int = Field(20, ge=1, le=100)
    cursor: str | None = None

PageDep = Annotated[PageParams, Query()]   # query params desde un modelo (FastAPI ≥ 0.115)
```
- Dependencias con `yield` para recursos por request (sesión DB). Por defecto el código tras `yield` corre **después de enviar la respuesta**: no hagas `commit()` ahí (hazlo en el service) o usa `Depends(dep, scope="function")` si tu versión de FastAPI lo soporta.
- Servicios como dependencia: `def get_order_service(session: SessionDep) -> OrderService: return OrderService(session)`.
- Dependencias a nivel de router: `APIRouter(dependencies=[Depends(require_scope("orders:read"))])`.

## Router
```python
router = APIRouter(prefix="/orders", tags=["orders"])
ServiceDep = Annotated[OrderService, Depends(get_order_service)]

@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED,
             responses={409: {"model": Problem}})
async def create_order(payload: OrderCreate, service: ServiceDep, user: CurrentUser) -> OrderRead:
    return await service.create(payload, owner_id=user.id)

@router.get("/{order_id}", response_model=OrderRead, responses={404: {"model": Problem}})
async def get_order(order_id: UUID, service: ServiceDep) -> OrderRead:
    return await service.get(order_id)

@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(order_id: UUID, service: ServiceDep) -> None:
    await service.delete(order_id)
```
- `response_model` filtra campos: aunque devuelvas el objeto ORM, solo salen los del schema.
- Path params tipados (`UUID`, `int`) validan automáticamente (422 si no cumplen).
- Usa el return type annotation o `response_model`, no ambos contradictorios.

## Async correcto
| Situación | Usa |
|---|---|
| Driver/cliente async (asyncpg, httpx.AsyncClient, `ainvoke` de LangChain) | `async def` + `await` |
| Librería bloqueante (requests, boto3, pandas pesado) | `def` (threadpool) o `await run_in_threadpool(fn, ...)` |
| CPU intensivo | worker/cola (Celery, arq) o `ProcessPoolExecutor` |
| Tareas tras responder | `BackgroundTasks` (ligeras) o cola |
Nunca `time.sleep`, `requests.get` ni sesiones SQLAlchemy sync dentro de `async def`.

## Errores
- Services lanzan excepciones de dominio (`NotFoundError`, `ConflictError`); handlers las convierten a `application/problem+json` (RFC 9457).
- `HTTPException` solo en router/deps (p. ej. auth 401/403).
- Personaliza `RequestValidationError` para devolver problem details con `errors[]`.
- Nunca expongas el mensaje de excepciones inesperadas; loguéalas con request-id.

## Settings y lifespan
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")
    database_url: str
    llm_model: str = "anthropic:claude-sonnet-5"
    anthropic_api_key: SecretStr | None = None
    cors_origins: list[str] = []

@lru_cache
def get_settings() -> Settings:
    return Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.http = httpx.AsyncClient(timeout=10)
    yield
    await app.state.http.aclose()
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```
- En tests, sobreescribe `get_settings` con `app.dependency_overrides`.
- `@app.on_event("startup"/"shutdown")` está deprecado: usa `lifespan`.

## Endpoints LLM
Crea el modelo/agente/grafo en `lifespan` y exponlo con una dependencia. Streaming SSE:
```python
@router.post("/chat/stream")
async def chat_stream(body: ChatIn, request: Request, agent: AgentDep):
    async def events():
        async for chunk in agent.astream({"messages": [{"role": "user", "content": body.message}]},
                                         stream_mode="messages", version="v2"):
            if await request.is_disconnected():
                break
            token, _meta = chunk["data"]
            if token.text:
                yield f"data: {json.dumps({'token': token.text})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")
```
Detalle en `backend:langchain-chains` y `backend:langgraph-agents`.

## Antipatrones
- Devolver modelos ORM sin `response_model` (fuga de campos) o usar el modelo ORM como body.
- `async def` con llamadas bloqueantes; crear engine/cliente HTTP/LLM por request.
- `HTTPException` en servicios; `except Exception: pass`.
- `os.getenv` disperso; settings instanciados en import time sin caché.
- Paginación sin límite máximo; `limit` sin `le=`.
- Lazy loading de relaciones en async (lanza `MissingGreenlet`): usa `selectinload`.

## Checklist final
- [ ] Schemas Pydantic v2 separados para create/update/read; `from_attributes` en read.
- [ ] `response_model` y `status_code` explícitos; `responses` documentadas para errores.
- [ ] Dependencias con `Annotated`; sesión DB por request con `yield`.
- [ ] Sin llamadas bloqueantes en `async def`.
- [ ] Excepciones de dominio + handlers; formato de error consistente.
- [ ] Settings con pydantic-settings; recursos en `lifespan`.
- [ ] Router registrado con prefijo/versión y tags.
- [ ] Tests con `AsyncClient` + `dependency_overrides`; ruff y pytest en verde.
