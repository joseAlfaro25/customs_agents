# Plantillas de documentación

Los bloques externos usan `~~~~` para poder contener bloques de código dentro.

## README de app/servicio

~~~~markdown
# <nombre>

<Una línea: qué es y para quién.>

## Stack
Next.js · React · TypeScript · Tailwind   <!-- con las versiones reales del manifiesto -->

## Requisitos
- Node <versión> y pnpm <versión>  /  Python <versión> y uv

## Inicio rápido
```bash
pnpm install
cp .env.example .env.local   # completa los valores
pnpm dev                     # http://localhost:3000
```

## Scripts
| Comando | Qué hace |
|---|---|
| `pnpm dev` | Servidor de desarrollo |
| `pnpm test` | Tests unitarios |
| `pnpm lint` | ESLint |
| `pnpm build` | Build de producción |

## Variables de entorno
| Variable | Requerida | Descripción | Ejemplo |
|---|---|---|---|
| `DATABASE_URL` | Sí | Conexión a Postgres | `postgresql://user:pass@localhost:5432/app` |

## Estructura
```
src/
├── app/        # rutas
├── features/   # lógica por dominio
└── lib/        # utilidades compartidas
```

## Despliegue
<Cómo se despliega o link al runbook.>

## Documentación
- [Arquitectura](docs/architecture/overview.md)
- [ADRs](docs/adr/)
~~~~

## Runbook

~~~~markdown
# Runbook: <operación o servicio>

## Cuándo usarlo
<Síntoma o tarea.>

## Prerrequisitos
- Acceso a ...

## Pasos
1. ...
   Verificación: <comando y salida esperada>

## Rollback
1. ...

## Contactos / escalamiento
- ...
~~~~

## Documento de arquitectura de un subsistema

~~~~markdown
# <Subsistema>

## Propósito

## Diagrama
```mermaid
flowchart LR
  a[Componente A] --> b[Componente B]
```

## Componentes
| Componente | Responsabilidad | Código |
|---|---|---|

## Flujos principales

## Datos

## Decisiones relacionadas
- ADR-NNNN

## Limitaciones conocidas
~~~~

## CHANGELOG

~~~~markdown
# Changelog

## [Unreleased]
### Added
- Exportar pedidos a CSV desde el panel.

### Fixed
- El total ya no se redondea mal con descuentos del 100 %.

## [1.2.0] - 2026-09-01
...
~~~~
