---
name: typescript-patterns
description: "Patrones de TypeScript para frontend: tsconfig estricto, type vs interface, genéricos, narrowing, discriminated unions, utility types, satisfies, validación runtime con zod e inferencia, tipado de APIs y cómo evitar any. Usar al diseñar tipos o corregir errores de compilación."
---

# typescript-patterns

Patrones de tipado para proyectos React/Next.js. Referencia: **TypeScript 5.x–7.x** (7.0, el port nativo, salió en julio 2026; 6.0 fue la versión puente). **Verifica `typescript` en `package.json` y el `tsconfig.json` real** antes de proponer cambios: TS 7 elimina opciones (`baseUrl`, `moduleResolution: node10`, `target: es5`) y cambia defaults (`strict: true`, `types: []`).

## Cuándo aplicarla

- Diseñar tipos de dominio, props, respuestas de API o estado.
- Corregir errores de `tsc` o eliminar `any`/`as` inseguros.
- Endurecer o migrar `tsconfig.json`.
- Validar datos externos (formularios, API, env, `localStorage`) con zod.

## Paso 0: diagnóstico

```bash
npx tsc --noEmit -p .          # errores reales del proyecto (en Next: también `next build`)
npx tsc --showConfig           # config efectiva tras "extends"
```

Lee el error completo desde abajo (la última línea suele ser la causa). Nunca "arregles" con `any`, `@ts-ignore` o `as unknown as X`.

## tsconfig estricto

Mínimo recomendado (además de lo que genere el framework):

```jsonc
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,   // arr[i] y record[key] son T | undefined
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "exactOptionalPropertyTypes": true, // opcional: distingue ausente de undefined (puede ser ruidoso)
    "verbatimModuleSyntax": true,       // obliga a `import type`
    "isolatedModules": true,
    "moduleResolution": "bundler",
    "module": "esnext",
    "skipLibCheck": true,
    "noEmit": true,
    "paths": { "@/*": ["./src/*"] }     // sin baseUrl (eliminado en TS 7)
  }
}
```

Detalle por opción, diferencias entre TS 5/6/7 y configuración para Next.js, Vite y tests: [references/tsconfig.md](references/tsconfig.md).

## `type` vs `interface`

- `type` por defecto: uniones, intersecciones, mapped/conditional types, tuplas, props de componentes.
- `interface` cuando necesitas **declaration merging** (augmentar módulos: `declare module 'next-auth' { interface Session {...} }`) o jerarquías de objetos con `extends` en librerías públicas.
- Sé consistente con el proyecto; no mezcles sin motivo.

## Narrowing

```ts
function format(value: string | number | Date): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number') return value.toFixed(2)
  return value.toISOString()
}

// Type predicate reutilizable
function isDefined<T>(v: T | null | undefined): v is T {
  return v != null
}
const ids = items.map((i) => i.id).filter(isDefined) // string[]
// TS 5.5+ infiere predicates simples: .filter((x) => x != null) también estrecha

// Assertion function
function assert(condition: unknown, msg: string): asserts condition {
  if (!condition) throw new Error(msg)
}
```

Usa `in`, `instanceof`, `Array.isArray` y comparaciones con literales antes que casts.

## Discriminated unions

Modela estados imposibles como imposibles:

```ts
type RequestState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: Error }

function render<T>(state: RequestState<T>) {
  switch (state.status) {
    case 'idle': return null
    case 'loading': return 'Cargando…'
    case 'success': return state.data
    case 'error': return state.error.message
    default: return assertNever(state)
  }
}

function assertNever(x: never): never {
  throw new Error(`Caso no manejado: ${JSON.stringify(x)}`)
}
```

Props mutuamente excluyentes:

```ts
type LinkOrButton =
  | ({ as: 'link'; href: string } & Omit<ComponentProps<'a'>, 'href'>)
  | ({ as?: 'button'; href?: never } & ComponentProps<'button'>)
```

## Genéricos

```ts
// Inferencia desde el argumento; restricción mínima necesaria
function groupBy<T, K extends PropertyKey>(items: readonly T[], key: (item: T) => K): Record<K, T[]> {
  return items.reduce((acc, item) => {
    ;(acc[key(item)] ??= []).push(item)
    return acc
  }, {} as Record<K, T[]>)
}

// Componente genérico
type SelectProps<T> = {
  options: readonly T[]
  value: T | null
  getLabel: (o: T) => string
  onChange: (o: T) => void
}
export function Select<T>({ options, value, getLabel, onChange }: SelectProps<T>) { /* ... */ }

// const type parameter (TS 5.0+): infiere literales sin `as const` en la llamada
function defineRoutes<const T extends readonly string[]>(routes: T) { return routes }
const routes = defineRoutes(['/', '/about']) // readonly ['/', '/about']
```

- Si un genérico aparece una sola vez en la firma, probablemente sobra.
- Nombres descriptivos cuando hay varios (`TData`, `TError`).

## Utility types esenciales

| Tipo | Uso |
|---|---|
| `Partial<T>`, `Required<T>`, `Readonly<T>` | Variaciones de opcionalidad/mutabilidad |
| `Pick<T, K>`, `Omit<T, K>` | Subconjuntos (DTOs, props derivadas) |
| `Record<K, V>` | Diccionarios con claves conocidas |
| `ReturnType<F>`, `Parameters<F>`, `Awaited<T>` | Derivar de funciones existentes |
| `NonNullable<T>`, `Extract<T, U>`, `Exclude<T, U>` | Filtrar uniones |
| `ComponentProps<'button' \| typeof Comp>` | Props de elementos o componentes |
| `NoInfer<T>` (5.4+) | Evitar que un argumento participe en la inferencia |

Deriva tipos de una fuente de verdad (schema, constante, función) en lugar de duplicarlos.

## `satisfies` y `as const`

```ts
const statusColors = {
  active: 'green',
  paused: 'yellow',
  archived: 'gray',
} as const satisfies Record<Status, string>
// Valida exhaustividad contra Status y conserva los literales
type StatusColor = (typeof statusColors)[Status] // 'green' | 'yellow' | 'gray'
```

- `satisfies` valida sin ensanchar; `: Tipo` ensancha; `as Tipo` miente. Prefiere en ese orden: inferencia → `satisfies` → anotación → `as` (solo con justificación).
- Uniones desde arrays: `const ROLES = ['admin', 'user'] as const; type Role = (typeof ROLES)[number]`.
- Evita `enum` (no es *erasable*; incompatible con `erasableSyntaxOnly` y type stripping de Node): usa objetos `as const` o uniones literales.

## Validación runtime con zod

TypeScript no valida en runtime. Todo dato externo entra como `unknown` y se parsea. Referencia: **zod 4** (verifica versión; en v3 los formatos eran métodos `z.string().email()` y el mensaje era `message`).

```ts
import { z } from 'zod'

export const UserSchema = z.object({
  id: z.uuid(),
  email: z.email({ error: 'Email inválido' }),
  name: z.string().min(1),
  role: z.enum(['admin', 'user']),
  createdAt: z.coerce.date(),
})
export type User = z.infer<typeof UserSchema>          // tipo de salida
export type UserInput = z.input<typeof UserSchema>     // tipo de entrada (antes de coerce/transform)

const result = UserSchema.safeParse(data)
if (!result.success) {
  const { fieldErrors } = z.flattenError(result.error)  // v4 (en v3: result.error.flatten())
}
```

- Un schema por contrato, tipo inferido con `z.infer`; no escribas la interfaz a mano en paralelo.
- `safeParse` en bordes con feedback al usuario; `parse` donde un fallo es un bug (env al arrancar).
- v4: `z.strictObject()`/`z.looseObject()` en lugar de `.strict()`/`.passthrough()`; `.extend()` en lugar de `.merge()`.

## Tipado de APIs

```ts
// lib/api.ts
export async function fetchJson<T>(url: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) throw new ApiError(res.status, await res.text())
  return schema.parse(await res.json())
}

const users = await fetchJson('/api/users', z.array(UserSchema))
```

- Nunca `res.json() as User[]` sin validar si la fuente no está bajo tu control.
- Si hay OpenAPI/GraphQL, genera tipos (`openapi-typescript`, `graphql-codegen`) o comparte schemas zod entre cliente y servidor (monorepo, tRPC, Server Actions).
- Resultados esperados como valores: `type Result<T, E = string> = { ok: true; data: T } | { ok: false; error: E }`.

## Evitar `any`

| En lugar de | Usa |
|---|---|
| `any` para datos externos | `unknown` + zod/narrowing |
| `any` en genéricos | parámetro de tipo con restricción |
| `as X` para callar un error | corregir el tipo origen o type guard |
| `// @ts-ignore` | `// @ts-expect-error <motivo>` (falla si deja de ser necesario) |
| `Function`, `object` | firma concreta `(x: T) => U`, `Record<string, unknown>` |
| `!` (non-null) | narrowing explícito o `assert` |

Activa `@typescript-eslint/no-explicit-any`, `no-unsafe-*` y `no-floating-promises` (con type-aware linting) si el proyecto usa typescript-eslint.

## Checklist final

- [ ] `tsc --noEmit` sin errores; sin `any`, `@ts-ignore` ni casts nuevos injustificados.
- [ ] Tipos derivados de una única fuente (schema, constante, función).
- [ ] Datos externos validados en runtime.
- [ ] Estados modelados con discriminated unions y `switch` exhaustivo.
- [ ] `import type` para imports solo de tipos.
- [ ] Opciones de `tsconfig` compatibles con la versión de TypeScript instalada.

## Skills relacionadas

- `frontend:react-components` para tipar props y hooks.
- `frontend:nextjs-app-router` para `PageProps`, `RouteContext` y Server Actions.
- `core:coding-standards` para principios generales.
