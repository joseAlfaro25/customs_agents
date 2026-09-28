# Convenciones de archivos del App Router

Consulta esta tabla al crear rutas o cuando dudes de qué archivo especial usar. Extensiones válidas: `.js`, `.jsx`, `.ts`, `.tsx` (o las de `pageExtensions`).

## Archivos especiales

| Archivo | Tipo | Propósito | Notas |
|---|---|---|---|
| `layout.tsx` | Server (por defecto) | UI compartida que persiste entre navegaciones | Root layout obligatorio con `<html>` y `<body>`. Recibe `children` y `params` (Promise) |
| `page.tsx` | Server | UI única de la ruta; hace el segmento accesible | Recibe `params` y `searchParams` (Promises) |
| `loading.tsx` | Server | Fallback de `<Suspense>` del segmento | Se muestra al navegar mientras `page` resuelve |
| `error.tsx` | **Client** (`'use client'`) | Error boundary del segmento | Props: `error`, `retry` (16.3+), `reset` |
| `global-error.tsx` | **Client** | Errores del root layout | Define su propio `<html>`/`<body>`; sin `metadata` |
| `not-found.tsx` | Server | UI para `notFound()` y URLs no encontradas | En la raíz cubre 404 global |
| `forbidden.tsx` / `unauthorized.tsx` | Server | UI para `forbidden()`/`unauthorized()` | Experimental (`experimental.authInterrupts`); verifica soporte |
| `template.tsx` | Server | Como layout pero se remonta en cada navegación | Úsalo solo para animaciones/efectos por navegación |
| `default.tsx` | Server | Fallback de un slot paralelo | Obligatorio en cada `@slot` en Next 16 |
| `route.ts` | — | Route handler (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS) | No coexistir con `page.tsx` en el mismo segmento |
| `proxy.ts` | — | Intercepta requests (Next 16+) | Raíz del proyecto o `src/`; `middleware.ts` en ≤15 |
| `instrumentation.ts` | — | Observabilidad (`register`, `onRequestError`) | Raíz o `src/` |

## Archivos de metadata

| Archivo | Genera |
|---|---|
| `favicon.ico`, `icon.(png|svg|tsx)`, `apple-icon.(png|tsx)` | Iconos |
| `opengraph-image.(png|tsx)`, `twitter-image.(png|tsx)` | Imágenes OG (con `ImageResponse` de `next/og` en `.tsx`) |
| `sitemap.ts` | `/sitemap.xml` (`export default function sitemap(): MetadataRoute.Sitemap`) |
| `robots.ts` | `/robots.txt` (`MetadataRoute.Robots`) |
| `manifest.ts` | Web app manifest |

## Segmentos de carpeta

| Patrón | Ejemplo | URL |
|---|---|---|
| Estático | `app/about/page.tsx` | `/about` |
| Dinámico | `app/blog/[slug]/page.tsx` | `/blog/hola` → `{ slug: 'hola' }` |
| Catch-all | `app/docs/[...slug]/page.tsx` | `/docs/a/b` → `{ slug: ['a','b'] }` |
| Catch-all opcional | `app/shop/[[...slug]]/page.tsx` | `/shop` y `/shop/a/b` |
| Route group | `app/(marketing)/pricing/page.tsx` | `/pricing` |
| Carpeta privada | `app/blog/_components/` | No enrutable |
| Slot paralelo | `app/@modal/...` | Prop `modal` en el layout padre; no afecta URL |
| Intercepción | `(.)foto`, `(..)foto`, `(..)(..)foto`, `(...)foto` | Intercepta una ruta en el contexto actual (modales) |

## Jerarquía de renderizado de un segmento

```
<Layout>
  <Template>
    <ErrorBoundary fallback={<Error />}>
      <Suspense fallback={<Loading />}>
        <NotFoundBoundary fallback={<NotFound />}>
          <Page />
        </NotFoundBoundary>
      </Suspense>
    </ErrorBoundary>
  </Template>
</Layout>
```

Consecuencia: `error.tsx` **no** captura errores del `layout.tsx` del mismo segmento; ponlo en el segmento padre o usa `global-error.tsx`.

## Plantillas mínimas

```tsx
// loading.tsx
export default function Loading() {
  return <div role="status" aria-live="polite">Cargando…</div>
}
```

```tsx
// error.tsx (Next 16.3+: retry; en versiones previas usa reset)
'use client'

import { useEffect } from 'react'

export default function Error({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error) // sustituye por el reporter del proyecto (Sentry, etc.)
  }, [error])

  return (
    <div role="alert">
      <h2>Algo salió mal</h2>
      <button type="button" onClick={() => retry()}>Reintentar</button>
    </div>
  )
}
```

```tsx
// not-found.tsx
import Link from 'next/link'

export default function NotFound() {
  return (
    <div>
      <h2>No encontrado</h2>
      <Link href="/">Volver al inicio</Link>
    </div>
  )
}
```

```tsx
// @modal/default.tsx
export default function Default() {
  return null
}
```
