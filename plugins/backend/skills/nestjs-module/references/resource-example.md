# Recurso NestJS completo (TypeORM)

Ejemplo de referencia para un recurso `orders`. Adáptalo a las convenciones del proyecto (ORM, casing, prefijos). Para la variante Prisma, ver el final.

## entities/order.entity.ts
```ts
import { Column, CreateDateColumn, Entity, Index, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';

export enum OrderStatus {
  Pending = 'pending',
  Paid = 'paid',
  Cancelled = 'cancelled',
}

@Entity({ name: 'orders' })
@Index(['customerId', 'createdAt'])
export class Order {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column('uuid')
  customerId!: string;

  @Column({ length: 200 })
  description!: string;

  @Column('integer')
  amountCents!: number;

  @Column({ type: 'enum', enum: OrderStatus, default: OrderStatus.Pending })
  status!: OrderStatus;

  @CreateDateColumn({ type: 'timestamptz' })
  createdAt!: Date;

  @UpdateDateColumn({ type: 'timestamptz' })
  updatedAt!: Date;
}
```

## dto/order-response.dto.ts y update-order.dto.ts
```ts
import { ApiProperty, PartialType, PickType } from '@nestjs/swagger';
import { IsEnum, IsOptional } from 'class-validator';

export class OrderResponseDto {
  @ApiProperty({ format: 'uuid' }) id!: string;
  @ApiProperty({ format: 'uuid' }) customerId!: string;
  @ApiProperty() description!: string;
  @ApiProperty() amountCents!: number;
  @ApiProperty({ enum: OrderStatus }) status!: OrderStatus;
  @ApiProperty() createdAt!: Date;

  static fromEntity(o: Order): OrderResponseDto {
    return Object.assign(new OrderResponseDto(), {
      id: o.id, customerId: o.customerId, description: o.description,
      amountCents: o.amountCents, status: o.status, createdAt: o.createdAt,
    });
  }
}

export class UpdateOrderDto extends PartialType(PickType(CreateOrderDto, ['description'] as const)) {
  @ApiProperty({ enum: OrderStatus, required: false })
  @IsOptional()
  @IsEnum(OrderStatus)
  status?: OrderStatus;
}

export class OrderPageDto {
  @ApiProperty({ type: [OrderResponseDto] }) data!: OrderResponseDto[];
  @ApiProperty({ nullable: true, type: String }) nextCursor!: string | null;
}
```

## orders.service.ts
```ts
import { ConflictException, Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { LessThan, Repository } from 'typeorm';

@Injectable()
export class OrdersService {
  constructor(@InjectRepository(Order) private readonly orders: Repository<Order>) {}

  async create(dto: CreateOrderDto): Promise<OrderResponseDto> {
    const saved = await this.orders.save(this.orders.create(dto));
    return OrderResponseDto.fromEntity(saved);
  }

  async list(q: ListOrdersQueryDto): Promise<OrderPageDto> {
    // Cursor = createdAt ISO del último elemento (simplificado; en producción codifica createdAt+id)
    const rows = await this.orders.find({
      where: {
        ...(q.status && { status: q.status }),
        ...(q.cursor && { createdAt: LessThan(new Date(q.cursor)) }),
      },
      order: { createdAt: 'DESC', id: 'DESC' },
      take: q.limit + 1,
    });
    const hasMore = rows.length > q.limit;
    const page = rows.slice(0, q.limit);
    return {
      data: page.map(OrderResponseDto.fromEntity),
      nextCursor: hasMore ? page[page.length - 1].createdAt.toISOString() : null,
    };
  }

  async findOne(id: string): Promise<OrderResponseDto> {
    const order = await this.orders.findOneBy({ id });
    if (!order) throw new NotFoundException(`Order ${id} not found`);
    return OrderResponseDto.fromEntity(order);
  }

  async update(id: string, dto: UpdateOrderDto): Promise<OrderResponseDto> {
    const order = await this.orders.findOneBy({ id });
    if (!order) throw new NotFoundException(`Order ${id} not found`);
    if (order.status === OrderStatus.Cancelled) {
      throw new ConflictException('Cancelled orders cannot be modified');
    }
    return OrderResponseDto.fromEntity(await this.orders.save(this.orders.merge(order, dto)));
  }

  async remove(id: string): Promise<void> {
    const { affected } = await this.orders.delete({ id });
    if (!affected) throw new NotFoundException(`Order ${id} not found`);
  }
}
```

## orders.module.ts
```ts
@Module({
  imports: [TypeOrmModule.forFeature([Order])],
  controllers: [OrdersController],
  providers: [OrdersService],
  exports: [OrdersService],
})
export class OrdersModule {}
```

## common/filters/problem-details.filter.ts (RFC 9457)
```ts
import { ArgumentsHost, Catch, ExceptionFilter, HttpException, HttpStatus, Logger } from '@nestjs/common';
import type { Request, Response } from 'express';

@Catch()
export class ProblemDetailsFilter implements ExceptionFilter {
  private readonly logger = new Logger(ProblemDetailsFilter.name);

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const res = ctx.getResponse<Response>();
    const req = ctx.getRequest<Request>();

    const status = exception instanceof HttpException ? exception.getStatus() : HttpStatus.INTERNAL_SERVER_ERROR;
    const body = exception instanceof HttpException ? exception.getResponse() : undefined;
    const message = typeof body === 'object' && body && 'message' in body ? (body as any).message : undefined;

    if (status >= 500) this.logger.error(exception instanceof Error ? exception.stack : exception);

    res.status(status).type('application/problem+json').json({
      type: `https://api.example.com/problems/${HttpStatus[status]?.toLowerCase().replace(/_/g, '-') ?? 'error'}`,
      title: HttpStatus[status] ?? 'Error',
      status,
      detail: status >= 500 ? 'Unexpected error' : Array.isArray(message) ? 'Validation failed' : message,
      instance: req.originalUrl,
      ...(Array.isArray(message) && { errors: message }),
    });
  }
}
```
Si usas Fastify en lugar de Express, cambia los tipos a `FastifyRequest`/`FastifyReply` y usa `res.status(status).header('content-type', ...).send(...)`.

## Registro de TypeORM en AppModule
```ts
TypeOrmModule.forRootAsync({
  inject: [ConfigService],
  useFactory: (config: ConfigService) => ({
    type: 'postgres',
    url: config.getOrThrow<string>('DATABASE_URL'),
    autoLoadEntities: true,
    synchronize: false,
    migrations: ['dist/migrations/*.js'],
  }),
}),
```

## Variante Prisma
```ts
@Injectable()
export class PrismaService extends PrismaClient implements OnModuleInit {
  async onModuleInit() { await this.$connect(); }
}

@Global()
@Module({ providers: [PrismaService], exports: [PrismaService] })
export class PrismaModule {}

// En el service:
constructor(private readonly prisma: PrismaService) {}

async findOne(id: string) {
  const order = await this.prisma.order.findUnique({ where: { id } });
  if (!order) throw new NotFoundException(`Order ${id} not found`);
  return order;
}
```
Con Prisma 7 el cliente se genera en una ruta configurada (`output` del generator) y requiere un driver adapter (p. ej. `@prisma/adapter-pg`); importa `PrismaClient` desde esa ruta y verifica la versión en `package.json`. Ver `backend:database-patterns`.
