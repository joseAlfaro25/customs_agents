---
name: database-patterns
description: "Patrones de acceso a datos: TypeORM y Prisma en NestJS, SQLAlchemy 2.x async y Alembic en FastAPI; repositorios, transacciones, migraciones seguras, N+1, índices y paginación. Usar al crear o modificar modelos, consultas, migraciones o al diagnosticar rendimiento de base de datos."
---

# database-patterns

## Objetivo
Acceder a la base de datos de forma correcta, eficiente y segura: modelos bien tipados, consultas sin N+1, transacciones con límites claros, migraciones reversibles y sin downtime, e índices alineados con los patrones de consulta reales.

## Cuándo aplicarla
- Crear o cambiar entidades/modelos y sus migraciones.
- Escribir consultas con relaciones, filtros, paginación o agregaciones.
- Implementar operaciones que escriben en varias tablas.
- Investigar endpoints lentos o bloqueos en la base de datos.

## Antes de empezar
1. Carga `core:project-context`. Identifica ORM y versión en el manifiesto: `typeorm` (0.3.x), `@prisma/client`/`prisma` (6.x o 7.x), `sqlalchemy` (2.x) + `alembic`, driver (`pg`, `asyncpg`, `psycopg`). **Verifica la versión en el manifiesto del proyecto.**
2. Diferencias que importan:
   - **TypeORM 0.2 → 0.3**: `DataSource` sustituye a `Connection`/`ormconfig`; `findOne(id)` ya no existe (usa `findOneBy({ id })`).
   - **Prisma 6 → 7**: generator `prisma-client` con `output` obligatorio (el cliente ya no vive en `node_modules/@prisma/client`), driver adapter obligatorio (`@prisma/adapter-pg`), `prisma.config.ts` para la URL y la CLI, y `.env` no se carga automáticamente.
   - **SQLAlchemy 1.4 → 2.0**: `Mapped`/`mapped_column`, `select()` estilo 2.0, `session.execute(select(...))`/`session.scalars(...)`; `Query` legacy desaconsejado.
3. Revisa migraciones existentes para seguir su convención de nombres y ubicación.

## Principios comunes
- **La base de datos es la fuente de verdad del esquema** vía migraciones versionadas. Nunca `synchronize: true` (TypeORM), `prisma db push` ni `Base.metadata.create_all()` fuera de desarrollo local o tests.
- **Acceso encapsulado**: el service usa repositorio (TypeORM `Repository`, `PrismaService`, clase repository con `AsyncSession`); el controller/router nunca toca el ORM.
- **Transacciones cortas**: agrupan solo escrituras relacionadas. Nada de llamadas HTTP/LLM dentro de una transacción.
- **Consultas explícitas**: selecciona solo columnas necesarias en listados grandes; carga relaciones de forma intencional.
- **Paginación siempre**: `LIMIT` acotado y orden determinista (`created_at DESC, id DESC`). Cursor (keyset) para tablas grandes; `OFFSET` degrada con páginas profundas.
- **Integridad en la DB**: `NOT NULL`, `UNIQUE`, `FOREIGN KEY`, `CHECK`; no confíes solo en validaciones de la aplicación. Traduce violaciones (`23505` unique en Postgres) a 409.
- **Tiempos**: `timestamptz` en UTC; IDs UUID (v7 si la versión del stack lo soporta, para ordenación temporal) o bigint identity.

## NestJS + TypeORM (resumen)
```ts
// Transacción con DataSource
await this.dataSource.transaction(async (manager) => {
  const order = await manager.save(Order, manager.create(Order, dto));
  await manager.decrement(Product, { id: dto.productId }, 'stock', dto.quantity);
  return order;
});

// Evitar N+1: carga relaciones en una consulta
const orders = await this.orders.find({ where: { customerId }, relations: { items: true }, take: 20 });
// o QueryBuilder para control fino
const rows = await this.orders.createQueryBuilder('o')
  .leftJoinAndSelect('o.items', 'i')
  .where('o.customerId = :customerId', { customerId })   // siempre parámetros, nunca interpolación
  .orderBy('o.createdAt', 'DESC').take(20).getMany();
```
Migraciones: `npx typeorm migration:generate src/migrations/AddOrders -d src/data-source.ts` → revisar → `migration:run`. `migration:revert` para deshacer.

## NestJS + Prisma (resumen)
```ts
// Transacción interactiva
await this.prisma.$transaction(async (tx) => {
  const order = await tx.order.create({ data: dto });
  await tx.product.update({ where: { id: dto.productId }, data: { stock: { decrement: dto.quantity } } });
  return order;
});

// Evitar N+1: include/select
await this.prisma.order.findMany({
  where: { customerId }, include: { items: true }, orderBy: [{ createdAt: 'desc' }, { id: 'desc' }], take: 20,
});
```
Migraciones: `npx prisma migrate dev --name add_orders` (local, genera SQL) y `npx prisma migrate deploy` (CI/producción). Revisa el SQL en `prisma/migrations/*/migration.sql` antes de commitear. Errores: `P2002` unique → 409, `P2025` no encontrado → 404.

## FastAPI + SQLAlchemy 2.x async (resumen)
```python
engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=5)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Transacción explícita
async with session.begin():
    session.add(order)
    await session.execute(
        update(Product).where(Product.id == pid).values(stock=Product.stock - qty)
    )

# Evitar N+1 y lazy loading en async
stmt = (select(Order).where(Order.customer_id == cid)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc(), Order.id.desc()).limit(20))
orders = (await session.scalars(stmt)).all()
```
- `selectinload` para colecciones (1 query extra por relación), `joinedload` para many-to-one. Con async, un acceso lazy no cargado lanza `MissingGreenlet`; puedes declarar `lazy="raise"` en relaciones para detectarlo en desarrollo.
- Alembic: `alembic revision --autogenerate -m "add orders"` → revisar el script → `alembic upgrade head`; `alembic downgrade -1` para revertir. Para async, `env.py` usa `async_engine_from_config` + `connection.run_sync(do_run_migrations)` (plantilla `alembic init -t async`).

Guía detallada con modelos, repositorios genéricos, Unit of Work, configuración de Alembic async, TypeORM `DataSource` y Prisma 7: lee [references/orm-reference.md](references/orm-reference.md) cuando implementes la capa de datos desde cero o migres de versión.

## Migraciones seguras (zero-downtime)
| Cambio | Cómo hacerlo sin romper |
|---|---|
| Añadir columna obligatoria | 1) añadir nullable o con default; 2) backfill por lotes; 3) `SET NOT NULL` |
| Renombrar columna | expand/contract: nueva columna → escribir en ambas → migrar lecturas → borrar la vieja en otro release |
| Borrar columna | primero quitar su uso en el código (release), luego la migración |
| Crear índice en tabla grande (Postgres) | `CREATE INDEX CONCURRENTLY` (fuera de transacción: en Alembic `with op.get_context().autocommit_block():`; en Prisma edita el SQL; en TypeORM `transaction = false` en la migración) |
| Cambiar tipo | nueva columna + backfill + swap; evita `ALTER TYPE` que reescribe la tabla |
- Cada migración con `down`/`downgrade` funcional o marcada explícitamente como irreversible.
- Nunca edites una migración ya aplicada en entornos compartidos: crea otra.
- Separa migraciones de esquema y de datos grandes (backfills en jobs por lotes).

## Índices
- Indexa columnas en `WHERE`, `JOIN` y `ORDER BY` de consultas frecuentes; índice compuesto en el orden `igualdad → rango/orden` (p. ej. `(customer_id, created_at)`).
- Toda foreign key usada en joins necesita índice (Postgres no lo crea automáticamente).
- Unique parcial para reglas como "un solo activo por usuario": `CREATE UNIQUE INDEX ... WHERE status = 'active'`.
- `EXPLAIN (ANALYZE, BUFFERS)` antes y después; busca `Seq Scan` en tablas grandes y filas estimadas vs reales.
- No indexes todo: cada índice cuesta en escrituras. Elimina los no usados (`pg_stat_user_indexes`).
- Vectores (pgvector): índice HNSW o IVFFlat según volumen; ver `backend:langchain-rag`.

## Detectar N+1
- Síntoma: número de queries crece con el tamaño de la página. Activa logging SQL en local (`logging: true` en TypeORM, `log: ['query']` en Prisma, `echo=True` en SQLAlchemy) y cuenta queries por request.
- Patrones culpables: `for x in rows: await repo.find(...)`, `Promise.all(rows.map(r => repo.findOne(...)))`, acceso a relación lazy en serialización.
- Arreglo: carga relacionada (`relations`/`include`/`selectinload`), consulta `IN (...)` agrupada o DataLoader en GraphQL.

## Antipatrones
- SQL con interpolación de strings (`\`WHERE id = ${id}\``, `text(f"...")`, `$queryRawUnsafe`).
- Transacciones que abarcan llamadas externas o esperas de usuario.
- Sesión/`EntityManager` compartido entre requests o guardado en un singleton.
- `SELECT *` + filtrado en memoria; `count(*)` en cada listado de tablas enormes.
- Borrado físico donde el negocio necesita auditoría (considera soft delete con índice parcial).
- Migraciones autogeneradas aplicadas sin revisar (pueden borrar columnas por un rename).

## Checklist final
- [ ] Modelo tipado con constraints en DB (NOT NULL, FK, UNIQUE).
- [ ] Migración generada, revisada, reversible y segura para tablas grandes.
- [ ] Consultas parametrizadas; sin N+1 (verificado con logging de queries).
- [ ] Paginación con límite y orden determinista.
- [ ] Índices para los filtros/orden nuevos; FKs indexadas.
- [ ] Escrituras múltiples en transacción corta; errores de constraint traducidos a 409/404.
- [ ] Tests contra DB real de test (ver `backend:backend-testing`).
