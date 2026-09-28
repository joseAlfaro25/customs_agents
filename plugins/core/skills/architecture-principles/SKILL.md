---
name: architecture-principles
description: "Principios de arquitectura para apps web, APIs, mobile y sistemas con LLMs: límites de módulos, capas, dependencias, contratos, datos, escalabilidad y cuándo escribir un ADR. Cargar al diseñar una feature grande, un servicio nuevo, un cambio de modelo de datos o al evaluar una decisión técnica."
---

# architecture-principles

La arquitectura es el conjunto de decisiones **caras de cambiar**. El objetivo no es la pureza, sino que el sistema siga siendo fácil de cambiar.

## Principios

1. **Empieza simple.** Monolito modular antes que microservicios. Separa un servicio solo con una razón concreta: escalado independiente, equipo independiente, runtime distinto (p. ej. Python para LLM + Node para API), aislamiento de fallos.
2. **Límites por dominio, no por capa técnica.** `orders/`, `billing/`, `auth/` > `controllers/`, `services/` globales.
3. **Dependencias hacia adentro.** Dominio/lógica no depende de framework, DB ni HTTP. Framework → aplicación → dominio.
4. **Contratos explícitos** entre módulos y servicios: tipos exportados, DTOs, OpenAPI, eventos versionados. Nadie accede a las tablas de otro módulo.
5. **Reversibilidad.** Prefiere decisiones fáciles de revertir; para las difíciles, ADR.
6. **Diseña para el fallo.** Timeouts, reintentos idempotentes, degradación, observabilidad desde el día uno.

## Capas de referencia

```
Presentación   → controllers (Nest), routers (FastAPI), pages/components (Next), screens (Expo)
Aplicación     → services / use cases: orquestan, transacciones, autorización
Dominio        → entidades, reglas de negocio puras, errores de dominio
Infraestructura→ repositorios, clientes HTTP, colas, LLM providers, storage
```

- Controllers/routers **delgados**: validan entrada, llaman al servicio, mapean salida.
- La lógica de negocio no vive en componentes React ni en controllers.
- En pequeño, aplicación + dominio pueden ser el mismo `service`; sepáralos cuando crezca.

## Guías por stack

| Stack | Estructura recomendada | Skill |
|---|---|---|
| Next.js | `app/` solo rutas; lógica en `features/<dominio>/` o `lib/`; Server Components para datos, Client solo para interactividad | `frontend:nextjs-app-router` |
| NestJS | Un módulo por dominio; providers inyectados; módulos comunicados por servicios exportados | `backend:nestjs-module` |
| FastAPI | `app/<dominio>/{router,schemas,service,repository}.py`; dependencias con `Depends` | `backend:fastapi-endpoint` |
| LLM / agentes | LLM detrás de un servicio; prompts versionados; grafo LangGraph como unidad de orquestación; tracing con LangSmith | `backend:langgraph-agents`, `backend:langsmith-observability` |
| Expo | `app/` rutas; `features/` lógica; capa `api/` tipada compartida | `mobile:expo-router-navigation` |
| Infra | IaC por entorno, módulos reutilizables, estado remoto | `devops:terraform` |

## Datos

- Un dueño por dato (un módulo/servicio escribe en su tabla).
- Migraciones versionadas y compatibles hacia atrás (expand → migrate → contract) para desplegar sin downtime.
- Define consistencia requerida: ¿transacción, o eventual con eventos/outbox?
- Índices según patrones de consulta reales; pagina todo listado.

## APIs y contratos

- Diseña el contrato antes de implementar (`backend:api-designer`).
- Versiona cambios incompatibles; los clientes mobile viven meses con versiones viejas.
- Un solo formato de error en toda la API.
- Tipos compartidos: genera clientes desde OpenAPI o comparte un paquete de tipos en el monorepo; no dupliques a mano.

## Sistemas con LLM

- Trata al LLM como una dependencia externa lenta, cara y no determinista: timeouts, reintentos, caché, límites de costo.
- Salida estructurada validada (schema) antes de usarla.
- Separa: prompts (versionados), herramientas (permisos mínimos), orquestación (grafo), memoria/estado (checkpointer), evaluación (datasets en LangSmith).
- Human-in-the-loop para acciones irreversibles.

## Atributos de calidad a evaluar

Para cada diseño responde brevemente: rendimiento, escalabilidad, disponibilidad, seguridad, observabilidad, costo, mantenibilidad, testabilidad. Identifica cuál es **el** atributo que manda en este caso.

## ADRs

Escribe un ADR cuando la decisión: afecta a varios módulos o servicios, introduce/quita una tecnología, cambia el modelo de datos o contratos públicos, o sería difícil de revertir.

- Ubicación: `docs/adr/NNNN-titulo-en-kebab.md` (sigue la numeración existente).
- Plantilla: [references/adr-template.md](references/adr-template.md).
- Estados: Propuesto → Aceptado → (Reemplazado por NNNN | Deprecado). Los ADRs no se editan: se reemplazan.

Para diagramas usa Mermaid dentro del markdown (C4 contexto/contenedores, secuencia para flujos). Ver [references/diagrams.md](references/diagrams.md).

## Antipatrones

- Microservicios para un equipo de 3 personas sin necesidad concreta.
- "Shared" o "common" que todos importan y nadie posee.
- Lógica de negocio en controllers, componentes o prompts.
- Acceso cruzado a tablas entre módulos.
- Elegir tecnología por moda sin ADR ni prueba de concepto.
- Diseñar sin mirar lo existente.
