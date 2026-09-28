# Caching y revalidación por versión de Next.js

Lee este archivo antes de tocar caché, revalidación o rendering estático/dinámico. Primero confirma la versión de `next` en `package.json` y si `next.config` tiene `cacheComponents: true`.

## Next.js 14 (modelo implícito)

- `fetch` en Server Components: cacheado por defecto (`force-cache`).
- GET route handlers: cacheados por defecto si no usan request-time APIs.
- Router cache del cliente: páginas reutilizadas 30 s (dinámicas) / 5 min (estáticas).
- `params`, `searchParams`, `cookies()`, `headers()`: síncronos.
- Opt-out: `cache: 'no-store'`, `export const dynamic = 'force-dynamic'`, `export const revalidate = 0`.

## Next.js 15 (sin caché por defecto)

- `fetch` **no** se cachea por defecto. Opt-in: `fetch(url, { cache: 'force-cache' })` o `{ next: { revalidate: 3600, tags: ['x'] } }`.
- GET route handlers **no** se cachean por defecto. Opt-in: `export const dynamic = 'force-static'`.
- Router cache: `staleTimes.dynamic` por defecto 0 para páginas.
- Request APIs asíncronas: `await params`, `await searchParams`, `await cookies()`, `await headers()`, `await draftMode()` (con acceso síncrono temporal con warning).
- Funciones no-fetch: `unstable_cache(fn, keyParts, { tags, revalidate })`.
- Dedupe dentro de un render: `cache` de React.
- Invalidación: `revalidateTag(tag)`, `revalidatePath(path, type?)`.
- `after()` de `next/server` (estable en 15.1) para trabajo tras enviar la respuesta.

## Next.js 16 sin Cache Components ("modelo previo")

Mismo comportamiento que 15, con cambios:

- Acceso síncrono a `params`/`searchParams`/`cookies()`/`headers()` **eliminado**.
- `revalidateTag(tag, profile)` exige un segundo argumento (`'max'` recomendado, `'hours'`, `'days'`, o `{ expire: segundos }`). La forma de un argumento está deprecada.
- Nuevas APIs en Server Actions: `updateTag(tag)` (read-your-writes) y `refresh()`.
- Route segment config sigue disponible: `dynamic`, `revalidate`, `fetchCache`.

```ts
// lib/data.ts (modelo previo)
export async function getUser(id: string) {
  const res = await fetch(`${process.env.API_URL}/users/${id}`, {
    next: { revalidate: 3600, tags: [`user:${id}`] },
  })
  if (!res.ok) throw new Error('Failed to fetch user')
  return res.json() as Promise<User>
}
```

## Next.js 16 con Cache Components (`cacheComponents: true`)

Activación en `next.config.ts`:

```ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  cacheComponents: true,
  // partialPrefetching: true, // 16.3+, opt-in para Partial Prefetching
}

export default nextConfig
```

Principios:

1. **Dinámico por defecto**: todo código async se ejecuta en request time salvo que lo cachees.
2. **Caché explícita** con la directiva `'use cache'` a nivel de función, componente o archivo.
3. **Partial Prerendering por defecto**: el static shell incluye contenido estático, resultados `'use cache'` y fallbacks de `<Suspense>`; lo demás hace streaming.
4. El dev overlay marca "blocking route" cuando un acceso runtime o no cacheado no está dentro de `<Suspense>`.

### `'use cache'`, `cacheLife`, `cacheTag`

```ts
import { cacheLife, cacheTag } from 'next/cache'

export async function getCategories() {
  'use cache'
  cacheLife('days')            // perfiles: 'seconds' | 'minutes' | 'hours' | 'days' | 'weeks' | 'max' | custom
  cacheTag('categories')
  return db.category.findMany()
}
```

- Empareja cada `'use cache'` con un `cacheLife`; sin él aplica el perfil `default`.
- Argumentos y closures forman la cache key y deben ser serializables.
- Perfiles personalizados en `next.config` → `cacheLife: { editorial: { stale, revalidate, expire } }`.
- `'use cache'` al inicio de un archivo cachea todos sus exports.

### Runtime data (cookies, headers, searchParams, params no conocidos)

```tsx
import { Suspense } from 'react'
import { cookies } from 'next/headers'

export default function Page() {
  return (
    <>
      <StaticHeader />
      <Suspense fallback={<CartSkeleton />}>
        <Cart />
      </Suspense>
    </>
  )
}

async function Cart() {
  const sessionId = (await cookies()).get('session')?.value
  return <CartItems sessionId={sessionId} />
}

async function CartItems({ sessionId }: { sessionId?: string }) {
  'use cache'
  cacheLife('minutes')
  const items = sessionId ? await getCart(sessionId) : []
  return <ul>{items.map((i) => <li key={i.id}>{i.name}</li>)}</ul>
}
```

- Lee el valor runtime fuera y pásalo como argumento al componente/función cacheada.
- `'use cache: private'`: permite leer cookies/headers directamente; el resultado vive solo en el navegador (prefetch).
- `'use cache: remote'`: guarda en un cache handler compartido y durable (útil con alta tasa de acierto en serverless).
- Para no bloquear el shell, pasa la Promise de `params` hacia abajo y haz `await` dentro de un `<Suspense>`.

### Valores no deterministas

`Math.random()`, `Date.now()`, `new Date()`, `crypto.randomUUID()` en render: usa `await connection()` (de `next/server`) dentro de un componente envuelto en `<Suspense>`, o muévelos dentro de `'use cache'` si un valor compartido es aceptable.

### Invalidación

| API | Dónde | Semántica |
|---|---|---|
| `updateTag(tag)` | Solo Server Actions | Expira y lee fresco en la misma request (formularios, ajustes de usuario) |
| `revalidateTag(tag, 'max')` | Server Actions, route handlers | Stale-while-revalidate: sirve lo cacheado y regenera en segundo plano |
| `revalidatePath('/ruta')` | Server Actions, route handlers | Invalida todo lo de una ruta |
| `refresh()` | Solo Server Actions | Refresca datos **no** cacheados (contadores, métricas); no toca la caché |
| `router.refresh()` | Cliente | Re-solicita el RSC payload de la ruta actual |

### Route segment config con Cache Components

`dynamic`, `revalidate` y `fetchCache` pertenecen al modelo previo. Con `cacheComponents` exprésalo con `'use cache'` + `cacheLife` y `<Suspense>`. Si el proyecto aún los tiene, migra con la guía oficial "Migrating to Cache Components" (`/docs/app/guides/migrating-to-cache-components`).

## Next.js 16.3: novedades relevantes

- `retry()` estable en `error.tsx` (en 16.2 era `unstable_retry`; en ≤16.1 solo `reset()`).
- `catchError` de `next/error` para error boundaries a nivel de componente que no interfieren con `notFound`/`redirect`.
- Root params: `import { lang } from 'next/root-params'` para leer params del root layout desde cualquier Server Component.
- `partialPrefetching: true` (opt-in) y helper de Playwright `instant()` de `@next/playwright`.
- `next build` puede usar TypeScript 7 para type checking.

## Diagnóstico rápido

- "Mi página no se actualiza" → ¿versión 14 con `fetch` cacheado por defecto? ¿tag invalidado con la API correcta? ¿router cache del cliente?
- "Blocking route" en dev (16 + cacheComponents) → envuelve el acceso runtime en `<Suspense>` o cachéalo.
- "Error: Route used `searchParams` synchronously" → añade `await` (codemod `next-async-request-api`).
- Build falla por `default.js` ausente → añade `default.tsx` en cada slot `@paralelo` (Next 16).
