---
name: coding-standards
description: "Estándares generales de código para cualquier stack (TypeScript y Python): naming, funciones, manejo de errores, validación, seguridad, dependencias y verificación. Cargar al escribir, modificar o refactorizar código, junto con la skill específica del stack."
---

# coding-standards

Reglas transversales. La skill del stack (p. ej. `backend:fastapi-endpoint`) añade las específicas; **las reglas del proyecto (CLAUDE.md, linters) ganan sobre ambas**.

## Principios

1. **Consistencia antes que preferencia.** Imita el código vecino: estructura, naming, librerías, estilo de errores. Un patrón "mejor" que rompe la consistencia es peor.
2. **Cambio mínimo que resuelve la tarea.** Nada de refactors, renombres o "mejoras" no pedidas en el mismo cambio. Si ves algo que arreglar, anótalo en la salida.
3. **Legible > ingenioso.** Código obvio, nombres que explican, flujo lineal con early returns.
4. **Sin código muerto ni especulativo.** No agregues parámetros, flags o abstracciones "por si acaso" (YAGNI). Abstrae a la tercera repetición, no a la primera.
5. **Frontera explícita.** Valida en los bordes (request HTTP, formulario, variables de entorno, respuesta de LLM, archivo externo); dentro del sistema confía en los tipos.

## Naming

| Elemento | TypeScript | Python |
|---|---|---|
| Variables / funciones | `camelCase` | `snake_case` |
| Clases / tipos / componentes | `PascalCase` | `PascalCase` |
| Constantes de módulo | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` |
| Archivos | lo que use el proyecto (`kebab-case.ts`, `PascalCase.tsx` para componentes) | `snake_case.py` |
| Booleanos | `isX`, `hasX`, `canX`, `shouldX` | `is_x`, `has_x` |

- Nombres por **intención de dominio** (`overdueInvoices`), no por tipo (`list2`, `data`, `tmp`).
- Funciones = verbo (`calculateTotal`, `send_invoice`). Evita `handle`, `process`, `manage` sin complemento.
- Sin abreviaturas salvo las universales (`id`, `url`, `db`, `api`).

## Funciones y módulos

- Una función hace una cosa; si necesitas "y" para describirla, divídela.
- Máximo ~3 parámetros posicionales; más → objeto/kwargs con nombre.
- Early return en vez de `if` anidados.
- Funciones puras para lógica de negocio; efectos (DB, red, disco, tiempo, aleatoriedad) en los bordes e inyectados → testeables.
- Sin estado global mutable. Configuración vía settings tipados, no `process.env`/`os.environ` dispersos.

## Tipos

- **TypeScript**: `strict: true`. Prohibido `any` (usa `unknown` + narrowing). Sin `as` para silenciar errores; sin `!` salvo con justificación. Tipos inferidos desde el schema (`z.infer`) en vez de duplicarlos.
- **Python**: type hints en toda firma pública; modelos Pydantic en fronteras; `from __future__ import annotations` si el proyecto lo usa. Nada de `dict` sin tipar para datos estructurados.

## Manejo de errores

- Nunca tragar errores (`catch {}` / `except: pass`). Si capturas: añade contexto y relanza, o maneja de verdad.
- Captura lo más específico posible (`except ValueError`, no `except Exception`) salvo en el borde de más alto nivel.
- Errores de dominio con tipos propios (`InvoiceNotFoundError`) y traducción a HTTP en una sola capa (filter de Nest, exception handler de FastAPI, error boundary en React).
- Mensajes útiles para quien depura; nunca expongas stack traces ni datos internos al cliente.
- Operaciones con red: timeout explícito y reintentos solo para errores transitorios e idempotentes.

## Seguridad (obligatorio)

- **Secretos**: nunca en código, tests, logs ni commits. Solo variables de entorno / gestor de secretos. Actualiza `.env.example` con el nombre, sin valor.
- **Entrada**: toda entrada externa se valida (schema) y se trata como no confiable, incluida la salida de un LLM.
- **SQL**: solo consultas parametrizadas / ORM. Nunca concatenar strings.
- **Auth**: verificar autorización en el servidor en cada operación (no confiar en el cliente ni en que la UI oculte el botón).
- **Frontend**: no usar `dangerouslySetInnerHTML` con contenido no sanitizado; no exponer secretos en variables `NEXT_PUBLIC_*` / `EXPO_PUBLIC_*`.
- **Logs**: sin PII, tokens ni contraseñas.
- **LLM**: prompt injection es entrada no confiable; tools con permisos mínimos; no ejecutar código/SQL generado sin sandbox o validación.

## Dependencias

- Antes de agregar una: ¿ya hay algo en el proyecto o en la stdlib que lo haga? ¿Está mantenida? ¿Licencia compatible?
- Agrega con el gestor del proyecto y confirma con el usuario si no estaba en la tarea.

## Comentarios

- Explican **por qué**, no qué. El qué lo dicen los nombres.
- `TODO` solo con contexto (`TODO(ticket-123): ...`). No dejes código comentado.
- Docstrings/TSDoc en APIs públicas de librerías y funciones no obvias (ver `core:documentation-standards`).

## Verificación antes de dar por terminado

Ejecuta lo que el proyecto tenga (detectado con `core:project-context`), en este orden, y reporta el resultado real:

1. Formato (si no lo hace un hook).
2. Typecheck: `tsc --noEmit` / `mypy` / `pyright`.
3. Lint: `eslint` / `ruff check`.
4. Tests afectados.
5. Build si el cambio afecta configuración, rutas o bundling.

Si algo falla y no es causado por tu cambio, dilo explícitamente en vez de ocultarlo.

## Antipatrones

- Reescribir un archivo entero para un cambio de 3 líneas.
- Cambiar formato de archivos no relacionados (ruido en el diff).
- `// @ts-ignore`, `# type: ignore` sin explicación.
- Catch-all que devuelve `null`/`None` silenciosamente.
- Copiar/pegar lógica en vez de extraer tras la tercera vez.
- Nombres genéricos: `utils.ts` de 800 líneas, `helpers.py`, `common/`.
