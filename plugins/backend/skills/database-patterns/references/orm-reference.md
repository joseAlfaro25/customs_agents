# Referencia detallada de ORMs

Lee la sección del ORM que use el proyecto. Verifica siempre la versión en el manifiesto antes de copiar.

## 1. TypeORM 0.3.x (NestJS)

### data-source.ts (CLI de migraciones)
```ts
import 'dotenv/config';
import { DataSource } from 'typeorm';

export default new DataSource({
  type: 'postgres',
  url: process.env.DATABASE_URL,
  entities: ['src/**/*.entity.ts'],
  migrations: ['src/migrations/*.ts'],
  synchronize: false,
});
```
Scripts típicos en `package.json`:
```json
{
  "migration:generate": "typeorm-ts-node-commonjs migration:generate -d src/data-source.ts",
  "migration:run": "typeorm-ts-node-commonjs migration:run -d src/data-source.ts",
  "migration:revert": "typeorm-ts-node-commonjs migration:revert -d src/data-source.ts"
}
```
Uso: `npm run migration:generate -- src/migrations/AddOrders`.

### Relaciones
```ts
@Entity('orders')
export class Order {
  @PrimaryGeneratedColumn('uuid') id!: string;

  @ManyToOne(() => Customer, (c) => c.orders, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'customer_id' })
  customer!: Customer;

  @Index()
  @Column('uuid', { name: 'customer_id' })
  customerId!: string;

  @OneToMany(() => OrderItem, (i) => i.order, { cascade: ['insert'] })
  items!: OrderItem[];
}
```
- Declara la columna FK explícita (`customerId`) para filtrar sin join.
- Evita `eager: true` global; carga relaciones por consulta.

### Repositorio custom
```ts
@Injectable()
export class OrdersRepository {
  constructor(@InjectRepository(Order) private readonly repo: Repository<Order>) {}

  findPageByCustomer(customerId: string, limit: number, before?: Date) {
    const qb = this.repo.createQueryBuilder('o')
      .leftJoinAndSelect('o.items', 'i')
      .where('o.customerId = :customerId', { customerId })
      .orderBy('o.createdAt', 'DESC').addOrderBy('o.id', 'DESC')
      .take(limit + 1);
    if (before) qb.andWhere('o.createdAt < :before', { before });
    return qb.getMany();
  }
}
```
Nota: con `take` + joins de colecciones, TypeORM hace una subconsulta de IDs para paginar correctamente; revisa el SQL generado.

### Transacción con QueryRunner (control fino, locks)
```ts
const qr = this.dataSource.createQueryRunner();
await qr.connect();
await qr.startTransaction();
try {
  const product = await qr.manager.findOne(Product, { where: { id }, lock: { mode: 'pessimistic_write' } });
  // ...
  await qr.commitTransaction();
} catch (e) {
  await qr.rollbackTransaction();
  throw e;
} finally {
  await qr.release();
}
```

### Migración con índice concurrente
```ts
export class AddOrdersCustomerIndex1700000000000 implements MigrationInterface {
  transaction = false as const; // CREATE INDEX CONCURRENTLY no puede ir en transacción
  async up(q: QueryRunner) {
    await q.query('CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_orders_customer_created ON orders (customer_id, created_at DESC)');
  }
  async down(q: QueryRunner) {
    await q.query('DROP INDEX CONCURRENTLY IF EXISTS ix_orders_customer_created');
  }
}
```
Verifica en la versión instalada que `transaction = false` por migración está soportado (depende también de la opción `migrationsTransactionMode`).

## 2. Prisma (NestJS)

### schema.prisma (Prisma 7)
```prisma
generator client {
  provider = "prisma-client"
  output   = "../src/generated/prisma"
}

datasource db {
  provider = "postgresql"
}

model Order {
  id          String      @id @default(uuid()) @db.Uuid
  customerId  String      @map("customer_id") @db.Uuid
  customer    Customer    @relation(fields: [customerId], references: [id], onDelete: Cascade)
  description String      @db.VarChar(200)
  amountCents Int         @map("amount_cents")
  status      OrderStatus @default(PENDING)
  items       OrderItem[]
  createdAt   DateTime    @default(now()) @map("created_at") @db.Timestamptz

  @@index([customerId, createdAt(sort: Desc)])
  @@map("orders")
}
```
### prisma.config.ts (Prisma 7)
```ts
import 'dotenv/config';
import { defineConfig, env } from 'prisma/config';

export default defineConfig({
  schema: 'prisma/schema.prisma',
  migrations: { path: 'prisma/migrations' },
  datasource: { url: env('DATABASE_URL') },
});
```
### PrismaService con driver adapter (Prisma 7)
```ts
import { Injectable, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaPg } from '@prisma/adapter-pg';
import { PrismaClient } from '../generated/prisma/client';

@Injectable()
export class PrismaService extends PrismaClient implements OnModuleInit, OnModuleDestroy {
  constructor(config: ConfigService) {
    super({ adapter: new PrismaPg({ connectionString: config.getOrThrow('DATABASE_URL') }) });
  }
  async onModuleInit() { await this.$connect(); }
  async onModuleDestroy() { await this.$disconnect(); }
}
```
En Prisma 6 el generator es `prisma-client-js`, la URL va en `datasource db { url = env("DATABASE_URL") }` y el cliente se importa de `@prisma/client`. Comprueba la ruta exacta del import generado y el nombre de export del adapter en la documentación de la versión instalada.

### Paginación por cursor nativa
```ts
const rows = await prisma.order.findMany({
  take: limit + 1,
  ...(cursor && { cursor: { id: cursor }, skip: 1 }),
  orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
});
```

### Errores conocidos
```ts
import { Prisma } from '../generated/prisma/client'; // o '@prisma/client' en v6
if (e instanceof Prisma.PrismaClientKnownRequestError) {
  if (e.code === 'P2002') throw new ConflictException('Duplicate');
  if (e.code === 'P2025') throw new NotFoundException();
}
```

## 3. SQLAlchemy 2.x async + Alembic (FastAPI)

### Modelos con relaciones
```python
class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    orders: Mapped[list["Order"]] = relationship(back_populates="customer", lazy="raise")

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    customer: Mapped[Customer] = relationship(back_populates="orders", lazy="raise")
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", lazy="raise")
```
`lazy="raise"` obliga a cargar relaciones explícitamente (`selectinload`), evitando N+1 silenciosos.

### Repositorio genérico
```python
from typing import Generic, TypeVar
ModelT = TypeVar("ModelT", bound=Base)

class Repository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id_) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        return obj

class OrderRepository(Repository[Order]):
    model = Order

    async def page_by_customer(self, customer_id: uuid.UUID, limit: int) -> list[Order]:
        stmt = (select(Order).where(Order.customer_id == customer_id)
                .options(selectinload(Order.items))
                .order_by(Order.created_at.desc(), Order.id.desc()).limit(limit))
        return list((await self.session.scalars(stmt)).all())
```

### Unit of Work explícito
```python
class UnitOfWork:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker

    async def __aenter__(self):
        self.session = self._sessionmaker()
        self.orders = OrderRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            await self.session.rollback()
        await self.session.close()

    async def commit(self):
        await self.session.commit()
```

### Locks y upserts (Postgres)
```python
product = (await session.execute(
    select(Product).where(Product.id == pid).with_for_update()
)).scalar_one()

from sqlalchemy.dialects.postgresql import insert
stmt = insert(Tag).values(name=name).on_conflict_do_nothing(index_elements=["name"])
await session.execute(stmt)
```

### Alembic async
Inicializa con `alembic init -t async migrations`. En `migrations/env.py`:
```python
from app.core.config import get_settings
from app.core.db import Base
import app.models  # noqa: F401  importa todos los modelos para autogenerate

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata
```
Añade `compare_type=True` en `context.configure(...)` para detectar cambios de tipo. Convención de nombres de constraints (necesaria para downgrades limpios):
```python
Base.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```
Índice concurrente en Alembic:
```python
def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index("ix_orders_status", "orders", ["status"], postgresql_concurrently=True)
```

### Tests
Crea el esquema con `alembic upgrade head` (o `Base.metadata.create_all` solo en tests) sobre una DB de test y envuelve cada test en una transacción con rollback. Ver `backend:backend-testing`.
