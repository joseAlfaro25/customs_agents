---
name: nextjs-app-router
description: "Convenciones de Next.js App Router: estructura de app/, layouts, route groups, rutas dinámicas, Server/Client Components, data fetching y caching, Server Actions, route handlers, metadata y proxy. Usar al crear, modificar o depurar rutas, páginas o caché en Next.js."
---

# nextjs-app-router

Guía práctica para construir con el App Router de Next.js. Referencia base: **Next.js 16.x** (16.3 es la estable a septiembre 2026) con React 19.x. **Verifica siempre la versión de `next` en `package.json` del proyecto**: el modelo de caché, `middleware` vs `proxy` y las props de `error.tsx` cambian entre versiones mayores.

## Cuándo aplicarla

- Crear o reorganizar rutas, layouts, route groups o rutas dinámicas.
- Decidir si un componente es Server o Client Component.
- Implementar data fetching, caché, revalidación o Server Actions.
- Crear route handlers (`route.ts`), `proxy.ts`/`middleware.ts`, metadata o SEO.
- Depurar errores de hidratación, "blocking route", caché obsoleta o props `params` síncronas.

## Paso 0: detectar versión y configuración

1. Lee `package.json` → versión de `next`, `react`, `typescript`.
2. Lee `next.config.(ts|js|mjs)` → ¿`cacheComponents: true`? ¿`reactCompiler`? ¿`partialPrefetching`?
3. ¿Existe `src/app` o `app`? ¿Hay `pages/` (proyecto mixto)? ¿`proxy.ts` o `middleware.ts`?
4. Lista las rutas existentes con `python3 "<carpeta de la skill nextjs-app-router>/scripts/list-routes.py" [ruta-del-proyecto]`.

El modelo de caché depende de la versión: lee [references/caching-by-version.md](references/caching-by-version.md) antes de tocar caché o revalidación.

## Estructura de `app/`

```
src/
├─ app/
│  ├─ layout.tsx                 # Root layout (obligatorio: <html> y <body>)
│  ├─ page.tsx                   # "/"
│  ├─ not-found.tsx              # 404 global
│  ├─ global-error.tsx           # Errores del root layout (define <html>/<body>)
│  ├─ (marketing)/               # Route group: no aparece en la URL
│  │  ├─ layout.tsx
│  │  └─ pricing/page.tsx        # "/pricing"
│  ├─ (app)/
│  │  ├─ layout.tsx              # Layout autenticado
│  │  └─ dashboard/
│  │     ├─ page.tsx             # "/dashboard"
│  │     ├─ loading.tsx          # Suspense boundary del segmento
│  │     ├─ error.tsx            # Error boundary (Client Component)
│  │     └─ _components/         # Carpeta privada: no genera ruta
│  ├─ blog/[slug]/page.tsx       # Dinámica: "/blog/hola"
│  ├─ docs/[...slug]/page.tsx    # Catch-all: "/docs/a/b"
│  ├─ shop/[[...filters]]/page.tsx # Catch-all opcional: "/shop" y "/shop/a"
│  └─ api/items/route.ts         # Route handler
├─ components/                   # UI compartida entre rutas
├─ lib/                          # Lógica, clientes, data access
└─ proxy.ts                      # (16+) o middleware.ts (≤15), junto a app/
```

Reglas:
- `app/` es para **routing**. Colocaliza lo específico de una ruta en `_components/`, `_lib/`; lo compartido va en `src/components` y `src/lib`.
- Una carpeta solo es ruta pública si contiene `page.tsx` o `route.ts`. No mezcles `page.tsx` y `route.ts` en el mismo segmento.
- Route groups `(nombre)` para layouts distintos sin afectar la URL. Dos grupos no pueden resolver la misma URL.
- Slots paralelos `@slot` requieren `default.tsx` en Next 16 (el build falla sin él).
- Tabla completa de archivos especiales y jerarquía de renderizado: [references/file-conventions.md](references/file-conventions.md).

## Páginas, layouts y params

Desde Next 15, `params` y `searchParams` son **Promises**; en Next 16 el acceso síncrono se eliminó. Usa los helpers globales `PageProps`, `LayoutProps` y `RouteContext` (generados por `next dev`/`next build`/`next typegen`, disponibles desde 15.5):

```tsx
// app/blog/[slug]/page.tsx
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { getPost } from '@/lib/posts'

export async function generateMetadata(props: PageProps<'/blog/[slug]'>): Promise<Metadata> {
  const { slug } = await props.params
  const post = await getPost(slug)
  return post ? { title: post.title, description: post.excerpt } : {}
}

export async function generateStaticParams() {
  const posts = await getPopularPosts()
  return posts.map((p) => ({ slug: p.slug }))
}

export default async function Page(props: PageProps<'/blog/[slug]'>) {
  const { slug } = await props.params
  const post = await getPost(slug)
  if (!post) notFound()
  return <article><h1>{post.title}</h1></article>
}
```

- Si el proyecto no tiene los helpers (Next < 15.5), tipa a mano: `{ params: Promise<{ slug: string }> }`.
- En Next 14 `params` era un objeto síncrono; no mezcles estilos. Hay codemod: `npx @next/codemod@latest next-async-request-api .`.
- Para compartir datos entre `generateMetadata` y la página sin duplicar la petición, envuelve la función de datos con `cache` de React.
- Un layout **no** recibe `searchParams` y no se re-renderiza al navegar entre sus hijos. Usa `template.tsx` solo si necesitas remontar en cada navegación.

## Server vs Client Components

Por defecto todo en `app/` es Server Component. Añade `'use client'` solo cuando necesites:
estado/efectos (`useState`, `useEffect`, `useActionState`), event handlers, APIs del navegador, o librerías que usan contexto/hooks.

Reglas:
- Empuja `'use client'` **a las hojas**: un botón interactivo, no la página entera.
- Un Client Component puede recibir Server Components como `children`/props (composición); no puede importarlos.
- Las props que cruzan la frontera deben ser serializables por RSC: primitivos, objetos planos, arrays, `Date`, `Map`, `Set`, Promises y Server Actions sí; funciones normales e instancias de clases no.
- Marca módulos de servidor con `import 'server-only'` (secretos, DB); y `import 'client-only'` para código solo de navegador.
- Providers de contexto: crea un `providers.tsx` con `'use client'` y úsalo en el layout envolviendo `children`.

```tsx
// app/(app)/dashboard/page.tsx (Server Component)
import { LikeButton } from './_components/like-button' // 'use client'
import { getStats } from '@/lib/stats'

export default async function Dashboard() {
  const stats = await getStats()
  return (
    <section>
      <h1>Dashboard</h1>
      <p>{stats.total} visitas</p>
      <LikeButton initialCount={stats.likes} />
    </section>
  )
}
```

## Data fetching

- Obtén datos en Server Components directamente (DB, ORM, `fetch`). No crees route handlers para consumirlos desde tu propio servidor.
- Evita cascadas: lanza peticiones independientes en paralelo con `Promise.all`, o pasa la Promise a un hijo dentro de `<Suspense>`.
- Streaming: envuelve partes lentas en `<Suspense fallback={...}>`; `loading.tsx` es el fallback de todo el segmento.
- Centraliza el acceso a datos en `src/lib/data/*` o un Data Access Layer con `import 'server-only'`, validando sesión y autorización ahí.
- Datos en cliente (polling, infinito, interacción): usa la librería del proyecto (TanStack Query, SWR) o `use(promise)` pasando una Promise desde el servidor.

## Caché y revalidación (resumen)

| Versión | Modelo |
|---|---|
| 14 | `fetch` cacheado por defecto (`force-cache`); GET route handlers cacheados |
| 15 | `fetch` y GET handlers **no** cacheados por defecto; opt-in con `cache: 'force-cache'`, `next: { revalidate, tags }`, `export const revalidate` |
| 16 sin `cacheComponents` | Igual que 15 ("modelo previo"); `revalidateTag(tag, profile)` exige segundo argumento |
| 16 con `cacheComponents: true` | Todo dinámico por defecto; caché explícita con `'use cache'` + `cacheLife` + `cacheTag`; runtime data dentro de `<Suspense>` |

Con Cache Components:

```ts
// src/lib/data/products.ts
import 'server-only'
import { cacheLife, cacheTag } from 'next/cache'

export async function getProducts(category: string) {
  'use cache'
  cacheLife('hours')
  cacheTag('products', `products:${category}`)
  return db.product.findMany({ where: { category } })
}
```

- Los argumentos y valores capturados forman la cache key; deben ser serializables.
- No leas `cookies()`/`headers()` dentro de `'use cache'`: léelos fuera y pasa el valor como argumento, o usa `'use cache: private'`.
- `Math.random()`, `Date.now()`, `crypto.randomUUID()` en render requieren `await connection()` + `<Suspense>` o estar dentro de `'use cache'`.
- Invalidación: `updateTag(tag)` (solo Server Actions, read-your-writes), `revalidateTag(tag, 'max')` (stale-while-revalidate), `revalidatePath(path)`, `refresh()` (refresca datos no cacheados).

Detalle, migración y opciones de segmento por versión: [references/caching-by-version.md](references/caching-by-version.md).

## Server Actions

```ts
// app/(app)/posts/actions.ts
'use server'

import { z } from 'zod'
import { updateTag } from 'next/cache'
import { redirect } from 'next/navigation'
import { requireUser } from '@/lib/auth'

const CreatePost = z.object({ title: z.string().min(3).max(120), body: z.string().min(1) })

export type CreatePostState = { errors?: Record<string, string[]>; message?: string }

export async function createPost(_prev: CreatePostState, formData: FormData): Promise<CreatePostState> {
  const user = await requireUser() // autoriza SIEMPRE dentro de la acción
  const parsed = CreatePost.safeParse(Object.fromEntries(formData))
  if (!parsed.success) return { errors: z.flattenError(parsed.error).fieldErrors }

  const post = await db.post.create({ data: { ...parsed.data, authorId: user.id } })
  updateTag('posts') // en Next 15: revalidateTag('posts')
  redirect(`/posts/${post.id}`) // fuera de try/catch: lanza internamente
}
```

Reglas:
- Una Server Action es un endpoint POST público: **valida entrada (zod) y autoriza** en cada una; no confíes en `proxy.ts`.
- Devuelve estados serializables para `useActionState`; lanza solo errores inesperados.
- `redirect()` y `notFound()` lanzan: no los envuelvas en `try/catch` (o re-lanza con `unstable_rethrow`).
- Usa `<form action={action}>` para mejora progresiva; en el cliente, `useActionState` y `useFormStatus` (ver `frontend:react-components`).

## Route handlers

```ts
// app/api/items/[id]/route.ts
import { NextResponse } from 'next/server'

export async function GET(_req: Request, ctx: RouteContext<'/api/items/[id]'>) {
  const { id } = await ctx.params
  const item = await getItem(id)
  if (!item) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  return NextResponse.json(item)
}
```

- Úsalos para webhooks, clientes externos, OAuth callbacks, descargas o streaming; no para leer datos desde tus propios Server Components.
- Valida `await req.json()` con zod; responde con códigos HTTP correctos.
- Con `cacheComponents`, los GET siguen el mismo modelo de prerender que las páginas.

## Metadata, imágenes y fuentes

- `export const metadata: Metadata` estático o `generateMetadata` dinámico, solo en Server Components (`layout`/`page`).
- Define `metadataBase` y `title: { default, template: '%s | Marca' }` en el root layout.
- Archivos de metadata: `favicon.ico`, `icon.png`, `opengraph-image.tsx`, `sitemap.ts`, `robots.ts`.
- `next/image`: `width`/`height` o `fill` + `sizes`; para la imagen LCP usa `loading="eager"` o `fetchPriority="high"` (en 16 `priority` está deprecado en favor de `preload`; en ≤15 usa `priority`); remotas vía `images.remotePatterns` (`images.domains` está deprecado). Next 16 cambió defaults: `qualities: [75]`, `minimumCacheTTL` 4 h, local src con query requiere `images.localPatterns`.
- `next/font` en el root layout, expuesto como variable CSS:

```tsx
import { Inter } from 'next/font/google'
const inter = Inter({ subsets: ['latin'], display: 'swap', variable: '--font-inter' })
// <html lang="es" className={inter.variable}>
```

## Proxy (antes middleware)

- Next 16: `proxy.ts` en la raíz (o `src/`), exporta `proxy` (o default) y `config.matcher`. Corre en Node.js; `runtime` no es configurable. `middleware.ts` sigue existiendo solo para Edge y está deprecado. Codemod: `npx @next/codemod@canary middleware-to-proxy .`.
- Next ≤15: `middleware.ts` exportando `middleware`.
- Úsalo para redirecciones, rewrites, headers, i18n y un chequeo optimista de sesión. **No** como única capa de autorización.
- Excluye siempre `_next/static`, `_next/image` y assets en el matcher.

## Variables de entorno

- Solo las prefijadas con `NEXT_PUBLIC_` llegan al cliente y se **inlinean en build**.
- Secretos: sin prefijo, leídos solo en módulos con `import 'server-only'`.
- Valida al arrancar con un esquema zod en `src/env.ts` (o `@t3-oss/env-nextjs` si el proyecto ya lo usa).
- `.env.local` no se commitea; documenta en `.env.example`. `serverRuntimeConfig`/`publicRuntimeConfig` se eliminaron en Next 16.

## Antipatrones

- `'use client'` en `layout.tsx` o `page.tsx` completos "por si acaso".
- `useEffect` + `fetch` para datos que podrían cargarse en el servidor.
- Llamar a tu propio `/api/*` desde un Server Component.
- Leer `params`/`searchParams` sin `await` o usar `React.use(params)` en Server Components.
- Secretos en variables `NEXT_PUBLIC_*` o importados en Client Components.
- Autorizar solo en `proxy.ts`/layout y no en la Server Action o el data layer.
- `revalidateTag('x')` de un argumento en Next 16 (deprecado) o `updateTag` fuera de Server Actions.
- `export const dynamic = 'force-dynamic'` como parche sin entender por qué la ruta es estática.

## Checklist final

- [ ] Versión de Next verificada; APIs usadas existen en esa versión.
- [ ] `'use client'` solo en hojas interactivas; `server-only` en módulos sensibles.
- [ ] `params`/`searchParams` tipados como Promise y con `await`.
- [ ] Cada ruta nueva tiene `loading`/`error`/`not-found` cuando aplica y `metadata`.
- [ ] Server Actions validan con zod, autorizan e invalidan la caché correcta.
- [ ] Sin cascadas de datos evitables; `<Suspense>` alrededor de lo lento o runtime.
- [ ] `tsc --noEmit`, lint y `next build` pasan (el build detecta errores de prerender).

## Skills relacionadas

- `frontend:react-components` para la UI cliente, formularios y React 19.
- `frontend:typescript-patterns` para tipar props, zod e inferencia.
- `frontend:frontend-testing` para testear páginas, acciones y e2e.
- `core:architecture-principles` y `core:project-context` para decisiones de estructura.
