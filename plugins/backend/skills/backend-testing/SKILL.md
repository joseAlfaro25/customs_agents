---
name: backend-testing
description: "Testing backend: Jest + @nestjs/testing (unit y e2e con supertest) y pytest + httpx AsyncClient/TestClient con dependency_overrides, fixtures y DB de test; incluye testing de código LLM con fake chat models. Usar al escribir, arreglar o ampliar tests de APIs NestJS/FastAPI o de cadenas y agentes."
---

# backend-testing

## Objetivo
Escribir tests rápidos, deterministas y significativos para APIs NestJS y FastAPI y para código LLM: unit con dobles de las dependencias, integración/e2e contra la app real con base de datos de test, y tests de cadenas/agentes sin llamar a proveedores reales.

## Cuándo aplicarla
- Al crear un endpoint, service, repositorio, cadena o grafo (tests en el mismo cambio).
- Al corregir un bug (primero un test que lo reproduzca).
- Al configurar la infraestructura de tests (DB de test, fixtures, CI).
- Al testear código que invoca LLMs.

## Antes de empezar
1. Carga `core:project-context` y `core:testing-strategy`.
2. Detecta runner y versiones: `jest`, `@nestjs/testing`, `supertest` (o `vitest`); `pytest`, `pytest-asyncio` o `anyio`, `httpx`. **Verifica la versión en el manifiesto del proyecto.** `pytest-asyncio` ≥ 0.23 cambió el manejo de event loops y en 1.x eliminó el fixture `event_loop`: usa `asyncio_default_fixture_loop_scope` en config.
3. Mira un test existente y replica ubicación, naming y helpers (factories, fixtures).

## Pirámide práctica
| Nivel | Qué cubre | Dependencias |
|---|---|---|
| Unit | services, reglas de negocio, nodos de grafo, parsers | mocks/fakes (repositorio, LLM) |
| Integración | repositorios + DB real, migraciones | DB de test (contenedor o local) |
| E2E/API | HTTP → controller → service → DB | app completa, DB de test, LLM fake |
| Evaluación LLM | calidad de respuestas/trayectorias | LLM real, dataset (fuera del CI rápido) |

## NestJS: unit test de un service
```ts
import { Test } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { NotFoundException } from '@nestjs/common';

describe('OrdersService', () => {
  let service: OrdersService;
  const repo = { findOneBy: jest.fn(), save: jest.fn(), create: jest.fn((x) => x), delete: jest.fn() };

  beforeEach(async () => {
    jest.resetAllMocks();
    const moduleRef = await Test.createTestingModule({
      providers: [OrdersService, { provide: getRepositoryToken(Order), useValue: repo }],
    }).compile();
    service = moduleRef.get(OrdersService);
  });

  it('throws NotFound when order does not exist', async () => {
    repo.findOneBy.mockResolvedValue(null);
    await expect(service.findOne('9b2d...')).rejects.toBeInstanceOf(NotFoundException);
  });
});
```
Con Prisma: `{ provide: PrismaService, useValue: { order: { findUnique: jest.fn() } } }` o `jest-mock-extended` (`mockDeep<PrismaClient>()`).

## NestJS: e2e con supertest
```ts
import { INestApplication, ValidationPipe } from '@nestjs/common';
import request from 'supertest';

describe('Orders (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] })
      .overrideProvider(LlmService).useValue({ summarize: jest.fn().mockResolvedValue('ok') })
      .overrideGuard(JwtAuthGuard).useValue({ canActivate: () => true })
      .compile();
    app = moduleRef.createNestApplication();
    // Replica la configuración global de main.ts (o extrae una función configureApp(app))
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
    await app.init();
  });

  afterAll(() => app.close());

  it('POST /orders validates body', () =>
    request(app.getHttpServer()).post('/orders').send({ amountCents: -1 }).expect(400));

  it('POST /orders creates', async () => {
    const res = await request(app.getHttpServer())
      .post('/orders').send({ customerId: CUSTOMER_ID, description: 'x', amountCents: 100 }).expect(201);
    expect(res.body).toMatchObject({ id: expect.any(String), status: 'pending' });
  });
});
```
- Extrae `configureApp(app)` desde `main.ts` y úsalo en e2e para no divergir (pipes, filters, prefix, versioning).
- `import request from 'supertest'` requiere `esModuleInterop`; si no, `import * as request from 'supertest'` (sigue lo que use el proyecto).
- Config de e2e en `test/jest-e2e.json`; ejecútalos con `npm run test:e2e`.

## FastAPI: tests async con httpx
```python
# tests/conftest.py
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import create_app
from app.core.db import get_session

@pytest.fixture
def app(db_session):
    app = create_app()
    async def _override_session():
        yield db_session
    app.dependency_overrides[get_session] = _override_session
    yield app
    app.dependency_overrides.clear()

@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```
```python
# tests/orders/test_router.py
async def test_create_order_returns_201(client):
    resp = await client.post("/api/v1/orders", json={"customer_id": str(CID), "description": "x", "amount_cents": 100})
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"

async def test_get_missing_order_returns_problem(client):
    resp = await client.get(f"/api/v1/orders/{uuid4()}")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
```
- Config en `pyproject.toml`: `[tool.pytest.ini_options] asyncio_mode = "auto"` y `asyncio_default_fixture_loop_scope = "function"` (pytest-asyncio), o marca con `@pytest.mark.anyio` si el proyecto usa anyio.
- `ASGITransport` **no ejecuta el `lifespan`**. Si la app depende de `app.state` creado en lifespan, usa `asgi-lifespan` (`LifespanManager(app)`) o sobreescribe las dependencias que lo leen.
- `TestClient` (sync, basado en httpx) sí ejecuta lifespan dentro de `with TestClient(app) as c:`; útil para tests sync simples, pero no lo mezcles con fixtures async de DB.
- `dependency_overrides` para auth (`get_current_user`), settings (`get_settings`) y servicios externos (LLM, HTTP).

## Base de datos de test
- Usa el mismo motor que producción (Postgres), nunca SQLite como sustituto si hay SQL específico (jsonb, pgvector, `ON CONFLICT`).
- Opciones: servicio en `docker compose` para CI/local o Testcontainers (`testcontainers[postgres]` en Python, `@testcontainers/postgresql` en Node).
- Esquema una vez por sesión (migraciones reales: `alembic upgrade head` / `prisma migrate deploy` / `migration:run`), aislamiento por test con transacción + rollback o truncado.
- Factories para datos (`factory_boy`/`polyfactory` en Python, funciones `buildOrder()` en TS); nada de depender de datos creados por otro test.

Fixtures completas (Postgres con Testcontainers, sesión con rollback por test, `asgi-lifespan`, e2e Nest con DB) y patrones de testing LLM: lee [references/fixtures-and-llm.md](references/fixtures-and-llm.md).

## Testing de código LLM (resumen)
- **Unit**: nunca llames al proveedor. Python: `GenericFakeChatModel(messages=iter([...]))` de `langchain_core.language_models.fake_chat_models`; para agentes con tools necesitas un fake que implemente `bind_tools` (subclase que devuelva `self`). JS: `FakeListChatModel` de `@langchain/core/utils/testing`.
- **Deterministas**: verifica que el prompt contiene lo esperado, que la salida estructurada se valida, que las tools reciben los args correctos y que los errores del modelo se manejan (timeouts, salida inválida).
- **Grafos**: nodos como funciones puras (input state → update); grafo completo con modelo fake + `InMemorySaver`; casos de `interrupt` y `Command(resume=...)`.
- **Endpoints**: sobreescribe la dependencia/provider que entrega el modelo/agente.
- **Calidad**: evaluaciones con LangSmith (`backend:langsmith-observability`) en un job separado, no en el unit suite.
- Desactiva tracing en unit (`LANGSMITH_TRACING=false`).

## Antipatrones
- Tests que dependen del orden de ejecución o de datos compartidos.
- Mockear lo que se está testeando (p. ej. mockear el repositorio en un test de integración del repositorio).
- `sleep` para esperar async; asserts sobre texto libre de un LLM real en CI.
- e2e sin la misma configuración global que producción (ValidationPipe, handlers).
- SQLite en tests cuando producción es Postgres con features específicas.
- Snapshots gigantes de respuestas que nadie revisa.

## Checklist final
- [ ] Cada endpoint nuevo tiene casos felices y de error (400/401/404/409/422).
- [ ] Services con unit tests y dependencias mockeadas por token/override.
- [ ] e2e/API tests contra DB de test aislada por test.
- [ ] Código LLM testeado con modelos fake; sin red en el suite rápido.
- [ ] Tests deterministas y rápidos; sin `sleep`.
- [ ] `npm test`/`npm run test:e2e` o `pytest` en verde localmente.
