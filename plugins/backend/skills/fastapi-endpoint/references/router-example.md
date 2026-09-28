# Router FastAPI completo (SQLAlchemy 2.x async)

Ejemplo de referencia para `orders`. Ajusta nombres, casing y organización a lo que ya exista en el proyecto.

## app/core/config.py
```python
from functools import lru_cache
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "api"
    environment: str = "local"
    database_url: str  # postgresql+asyncpg://user:pass@host:5432/db
    cors_origins: list[str] = []
    jwt_secret: SecretStr

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

## app/core/db.py
```python
from collections.abc import AsyncIterator
from typing import Annotated
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session   # al salir del `async with` se cierra; lo no confirmado se descarta

SessionDep = Annotated[AsyncSession, Depends(get_session)]
```
**Commit explícito en el service** (`await self.session.commit()`), no después del `yield`: en FastAPI actual el código tras `yield` se ejecuta por defecto **después de enviar la respuesta**, así que un commit ahí podría fallar cuando el cliente ya recibió un 201. Si quieres unit of work por request con commit en la dependencia, declara `Depends(get_session, scope="function")` (el cierre ocurre antes de enviar la respuesta); verifica que la versión de FastAPI del proyecto soporte `scope`.

## app/core/errors.py (RFC 9457)
```python
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None

class DomainError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    type = "https://api.example.com/problems/bad-request"
    title = "Bad Request"

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail

class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    type = "https://api.example.com/problems/not-found"
    title = "Not Found"

class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    type = "https://api.example.com/problems/conflict"
    title = "Conflict"

def _problem(status_code: int, body: dict) -> JSONResponse:
    return JSONResponse(body, status_code=status_code, media_type="application/problem+json")

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_handler(request: Request, exc: DomainError):
        return _problem(exc.status_code, {
            "type": exc.type, "title": exc.title, "status": exc.status_code,
            "detail": exc.detail, "instance": str(request.url.path),
        })

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        errors = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
        return _problem(422, {
            "type": "https://api.example.com/problems/validation", "title": "Validation failed",
            "status": 422, "instance": str(request.url.path), "errors": errors,
        })
```

## app/orders/models.py
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_customer_created", "customer_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID]
    description: Mapped[str] = mapped_column(String(200))
    amount_cents: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

## app/orders/schemas.py
```python
class OrderPage(BaseModel):
    data: list[OrderRead]
    next_cursor: str | None
```
(Más `OrderCreate`, `OrderUpdate`, `OrderRead` como en SKILL.md.)

## app/orders/service.py
```python
from datetime import datetime
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: OrderCreate) -> Order:
        order = Order(**data.model_dump())
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)   # carga server defaults (created_at)
        return order

    async def get(self, order_id: UUID) -> Order:
        order = await self.session.get(Order, order_id)
        if order is None:
            raise NotFoundError(f"Order {order_id} not found")
        return order

    async def list(self, limit: int, cursor: str | None, status: str | None) -> OrderPage:
        stmt = select(Order).order_by(Order.created_at.desc(), Order.id.desc()).limit(limit + 1)
        if status:
            stmt = stmt.where(Order.status == status)
        if cursor:
            stmt = stmt.where(Order.created_at < datetime.fromisoformat(cursor))
        rows = list((await self.session.scalars(stmt)).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        return OrderPage(
            data=[OrderRead.model_validate(r) for r in rows],
            next_cursor=rows[-1].created_at.isoformat() if has_more else None,
        )

    async def update(self, order_id: UUID, data: OrderUpdate) -> Order:
        order = await self.get(order_id)
        if order.status == "cancelled":
            raise ConflictError("Cancelled orders cannot be modified")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(order, field, value)
        await self.session.commit()
        return order

    async def delete(self, order_id: UUID) -> None:
        await self.session.delete(await self.get(order_id))
        await self.session.commit()
```

## app/orders/router.py
```python
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status

router = APIRouter(prefix="/orders", tags=["orders"])

def get_order_service(session: SessionDep) -> OrderService:
    return OrderService(session)

ServiceDep = Annotated[OrderService, Depends(get_order_service)]

@router.get("", response_model=OrderPage)
async def list_orders(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
):
    return await service.list(limit, cursor, status_filter)

@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, service: ServiceDep):
    return await service.create(payload)

@router.get("/{order_id}", response_model=OrderRead, responses={404: {"model": Problem}})
async def get_order(order_id: UUID, service: ServiceDep):
    return await service.get(order_id)

@router.patch("/{order_id}", response_model=OrderRead,
              responses={404: {"model": Problem}, 409: {"model": Problem}})
async def update_order(order_id: UUID, payload: OrderUpdate, service: ServiceDep):
    return await service.update(order_id, payload)

@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(order_id: UUID, service: ServiceDep) -> None:
    await service.delete(order_id)
```

## app/main.py
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    yield
    await engine.dispose()

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"])
    register_exception_handlers(app)
    app.include_router(orders_router, prefix="/api/v1")
    return app

app = create_app()
```
`expire_on_commit=False` evita que los atributos expiren tras `commit()` y se intente un lazy load fuera de contexto async al serializar.
