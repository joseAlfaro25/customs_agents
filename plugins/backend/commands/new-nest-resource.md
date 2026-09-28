---
description: "Genera un recurso NestJS completo (module, controller, service, DTOs, entity o modelo Prisma, migración, tests unit y e2e) siguiendo las convenciones del proyecto"
argument-hint: "<nombre-recurso> [campos, p. ej. title:string price:int]"
---

Genera un recurso NestJS a partir de: `$ARGUMENTS`

## 1. Validar el argumento
- El primer token de `$ARGUMENTS` es el nombre del recurso. Si `$ARGUMENTS` está vacío, **detente y pide** el nombre del recurso (y opcionalmente sus campos) antes de continuar.
- Normaliza: nombre de carpeta y rutas en kebab-case plural (`purchase-orders`), clases en PascalCase singular (`PurchaseOrder`, `PurchaseOrdersService`). Si el nombre es ambiguo o reservado, confirma con el usuario.
- Los tokens restantes, si existen, son campos `nombre:tipo` (tipos: `string`, `text`, `int`, `decimal`, `bool`, `date`, `uuid`, `enum(a|b)`; sufijo `?` = opcional). Si no hay campos, infiere un conjunto mínimo razonable y **muéstralo** en el plan.

## 2. Cargar contexto y skills
1. Carga la skill `core:project-context` y lee `CLAUDE.md`, `package.json`, `nest-cli.json` y `tsconfig.json`.
2. Carga `backend:nestjs-module`, `backend:database-patterns` y `backend:backend-testing`.
3. Detecta: versión de Nest, ORM (TypeORM o Prisma; si no hay ninguno, pregunta o genera el service con un repositorio en memoria marcado como TODO explícito), gestor de paquetes, ubicación de módulos (`src/`, `apps/<app>/src/` en monorepo), prefijo/versionado global y formato de errores.
4. Elige un módulo existente como referencia y replica su estilo (nombres, uso de ResponseDto, repositorio custom, paginación).
5. Comprueba que el recurso no existe ya (`src/<nombre>/`). Si existe, pregunta si ampliarlo en lugar de sobrescribir.

## 3. Plan
Presenta un plan breve con: archivos a crear/modificar, campos con validaciones, endpoints (`GET /<recurso>`, `GET /<recurso>/:id`, `POST`, `PATCH /:id`, `DELETE /:id`) con status codes, y la migración. Si el usuario no pidió confirmación explícita, continúa.

## 4. Implementar
1. **Modelo de datos**
   - TypeORM: `entities/<nombre>.entity.ts` con `@Entity`, UUID PK, `createdAt`/`updatedAt` `timestamptz`, índices para filtros previstos.
   - Prisma: añade el `model` a `schema.prisma` con `@@map` y `@map` según convención existente.
2. **DTOs** en `dto/`: `create-*.dto.ts` (class-validator + `@ApiProperty`), `update-*.dto.ts` (`PartialType` de `@nestjs/swagger`), `list-*-query.dto.ts` (limit con `@Max(100)`, cursor/page según el proyecto, filtros) y `*-response.dto.ts` si el proyecto no expone entidades.
3. **Service**: CRUD con `NotFoundException`/`ConflictException`, paginación con orden determinista, transacción si hay escrituras múltiples, traducción de errores de unicidad a 409.
4. **Controller**: rutas REST, `ParseUUIDPipe`, `@HttpCode(204)` en delete, decoradores Swagger (`@ApiTags`, respuestas tipadas), guards de auth si el resto de controllers los usa.
5. **Module**: `TypeOrmModule.forFeature([...])` o dependencia de `PrismaModule`; exporta el service.
6. **Registro**: importa el módulo en `AppModule` (o el módulo padre correspondiente).
7. **Migración**
   - TypeORM: `npm run migration:generate -- src/migrations/Create<Nombre>` (o el script equivalente del proyecto). Revisa el SQL generado.
   - Prisma: `npx prisma migrate dev --name create_<nombre>` (y `npx prisma generate` si no se ejecuta solo).
   - Si no hay base de datos disponible, genera la migración manualmente siguiendo el formato existente e indícalo.
8. **Tests**
   - `<nombre>.service.spec.ts`: casos de éxito, not found y conflicto con el repositorio/PrismaService mockeado.
   - `test/<nombre>.e2e-spec.ts`: validación (400), creación (201), obtención (200/404), borrado (204), usando la misma configuración global que `main.ts`.

## 5. Verificar
Ejecuta con el gestor del proyecto y corrige hasta que pase:
1. `npx tsc --noEmit` (o `npm run build`).
2. `npm run lint` (si existe).
3. `npm test -- <nombre>` y `npm run test:e2e -- <nombre>` (si hay e2e configurados y DB de test disponible; si no, indícalo).

## 6. Entregar
Resume: archivos creados/modificados, endpoints con status codes, migración y cómo aplicarla, resultado de cada verificación y supuestos tomados (campos inferidos, ORM, auth).
