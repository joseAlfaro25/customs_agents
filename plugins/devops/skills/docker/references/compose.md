# docker compose para desarrollo local

Objetivo: `docker compose up` levanta la app con recarga en caliente y sus dependencias (Postgres, Redis) con healthchecks. No es un despliegue de producción.

Convenciones:
- Archivo `compose.yaml` en la raíz del servicio (o del monorepo). Sin clave `version:` (obsoleta en Compose v2).
- Credenciales solo de desarrollo, leídas de `.env` (ignorado en git) con `.env.example` versionado. Nunca reutilices credenciales reales.
- Puertos de dependencias ligados a `127.0.0.1` para no exponerlos a la red local.
- `depends_on` con `condition: service_healthy` para que la app no arranque antes que la db.
- Volúmenes con nombre para datos persistentes; nada de bind mounts sobre `node_modules` o `.venv` del host.

## Plantilla (Node: Next.js o NestJS)

```yaml
name: myapp

services:
  app:
    build:
      context: .
      target: dev            # etapa dev del Dockerfile (ver dockerfiles.md, sección 6)
    ports:
      - "3000:3000"
    env_file:
      - path: .env
        required: false
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/app
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
        - action: rebuild
          path: package.json
        - action: rebuild
          path: pnpm-lock.yaml

  db:
    image: postgres:18
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      # Desde postgres:18 el volumen se monta en /var/lib/postgresql (antes /var/lib/postgresql/data)
      - pgdata:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:8-alpine
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

Para Next.js cambia `./src` por las carpetas reales (`./app`, `./components`, `./lib`) o sincroniza `.` con `ignore: [node_modules/, .next/]`.

## Variante Python (FastAPI / LangGraph)

```yaml
services:
  api:
    build:
      context: .
      target: dev
    ports:
      - "8000:8000"
    env_file:
      - path: .env
        required: false
    environment:
      DATABASE_URL: postgresql+psycopg://app:app@db:5432/app
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
    develop:
      watch:
        - action: sync
          path: ./app
          target: /app/app
        - action: rebuild
          path: uv.lock
```
(Reutiliza `db`, `redis` y `volumes` de la plantilla anterior.)

## Extras opcionales
- **pgvector** para RAG con LangChain: `image: pgvector/pgvector:pg18` en lugar de `postgres:18` (verifica la etiqueta).
- **Migraciones**: servicio `migrate` de un solo uso (`command: ["pnpm", "prisma", "migrate", "deploy"]` o `["alembic", "upgrade", "head"]`) y `app.depends_on.migrate.condition: service_completed_successfully`.
- **Perfiles** para herramientas que no siempre se necesitan: `profiles: ["tools"]` en `pgadmin`/`redis-insight`, activadas con `docker compose --profile tools up`.

## Comandos
```bash
docker compose config            # valida y muestra el archivo resuelto
docker compose up --build        # levantar
docker compose watch             # levantar con sync/rebuild automático
docker compose logs -f app
docker compose down              # parar (añade -v SOLO si el usuario quiere borrar los datos locales)
```
