---
description: "Genera un router FastAPI completo (schemas Pydantic v2, service, dependencias, modelo SQLAlchemy, migración Alembic y tests con httpx) siguiendo las convenciones del proyecto"
argument-hint: "<nombre-router> [campos, p. ej. title:str price:int]"
---

Genera un router FastAPI a partir de: `$ARGUMENTS`

## 1. Validar el argumento
- El primer token de `$ARGUMENTS` es el nombre del recurso. Si `$ARGUMENTS` está vacío, **detente y pide** el nombre (y opcionalmente los campos) antes de continuar.
- Normaliza: módulo/paquete en snake_case plural (`purchase_orders`), ruta en kebab-case plural (`/purchase-orders`), modelos en PascalCase singular (`PurchaseOrder`, `PurchaseOrderCreate`).
- Tokens restantes: campos `nombre:tipo` (`str`, `text`, `int`, `decimal`, `bool`, `date`, `datetime`, `uuid`, `enum(a|b)`; sufijo `?` = opcional). Si no hay, infiere un conjunto mínimo y muéstralo en el plan.

## 2. Cargar contexto y skills
1. Carga `core:project-context`; lee `CLAUDE.md`, `pyproject.toml`, el punto de entrada de la app, `alembic.ini` y `alembic/env.py` (o `migrations/env.py`).
2. Carga `backend:fastapi-endpoint`, `backend:database-patterns` y `backend:backend-testing`.
3. Detecta: versiones de FastAPI/Pydantic/SQLAlchemy, gestor (`uv`/`poetry`/`pip`), organización (por feature `app/<recurso>/` o por capas `app/routers|schemas|services|models`), cómo se obtiene la sesión (`get_session`/`SessionDep`), auth, prefijo/versión y formato de errores.
4. Si el proyecto aún no tiene SQLAlchemy, pregunta si añadirlo o generar el service sobre un repositorio en memoria marcado como pendiente.
5. Comprueba que el recurso no exista ya; si existe, pregunta si ampliarlo.

## 3. Plan
Presenta: archivos a crear/modificar, schemas con validaciones, endpoints (`GET /<recurso>`, `GET /<recurso>/{id}`, `POST`, `PATCH /{id}`, `DELETE /{id}`) con `response_model` y status codes, y la migración. Continúa salvo que el usuario haya pedido revisar antes.

## 4. Implementar
1. **Modelo** SQLAlchemy 2.x (`Mapped`, `mapped_column`), UUID PK, `created_at` `timestamptz` con `server_default`, índices para filtros previstos. Impórtalo donde Alembic lo descubra (el módulo de modelos que importa `env.py`).
2. **Schemas** Pydantic v2: `<X>Create`, `<X>Update` (todos opcionales), `<X>Read` (`from_attributes=True`), `<X>Page` (data + cursor/total según el proyecto).
3. **Service** async: CRUD con excepciones de dominio (`NotFoundError`, `ConflictError`) del proyecto, commit explícito, paginación con límite y orden determinista, `selectinload` si hay relaciones.
4. **Dependencias**: `get_<x>_service` y alias `Annotated`; reutiliza `SessionDep`, auth y paginación existentes.
5. **Router**: `APIRouter(prefix="/<ruta>", tags=["<recurso>"])`, `response_model`, `status_code` (201 en create, 204 en delete), `responses` para 404/409, `limit` con `le=100`.
6. **Registro**: `app.include_router(...)` con el prefijo/versión del proyecto.
7. **Migración**: `alembic revision --autogenerate -m "create <recurso>"` (con `uv run`/`poetry run` si aplica). Revisa el script: tipos, índices, `downgrade`. Si no hay DB accesible, escribe la migración a mano siguiendo el formato existente e indícalo.
8. **Tests** en `tests/<recurso>/`: create 201, validación 422, get 200/404, list con paginación, patch 200, delete 204; con `AsyncClient` + `ASGITransport` y `dependency_overrides` (sesión de test, auth).

## 5. Verificar
Ejecuta con el gestor del proyecto y corrige hasta que pase:
1. `ruff check .` y `ruff format --check .` (o el linter configurado).
2. Typecheck si está configurado (`mypy`/`pyright`).
3. `pytest tests/<recurso> -q` (indica si falta DB de test).
4. Si hay DB local: `alembic upgrade head` y `alembic downgrade -1` para probar la reversibilidad, luego vuelve a `head`.

## 6. Entregar
Resume: archivos creados/modificados, endpoints con `response_model` y status codes, migración y cómo aplicarla, resultado de cada verificación y supuestos (campos inferidos, auth, paginación).
