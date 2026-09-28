---
description: "Crea una ruta de Next.js App Router con page, loading, error y metadata (y not-found si es dinámica), adaptada a la versión de Next del proyecto. Úsalo para añadir una página nueva."
argument-hint: "<ruta> [descripción breve] (ej. /dashboard/settings, /blog/[slug], (marketing)/pricing)"
---

# /new-page

Argumentos recibidos: `$ARGUMENTS`

## 1. Validar argumentos

- El primer token de `$ARGUMENTS` es la ruta. Si `$ARGUMENTS` está vacío, **detente y pregunta** la ruta (p. ej. `/settings/profile`, `/blog/[slug]`), qué debe mostrar, de dónde vienen los datos y si requiere autenticación.
- Normaliza: quita la `/` inicial y final, segmentos en minúsculas kebab-case. Acepta segmentos especiales: `(grupo)`, `[param]`, `[...param]`, `[[...param]]`. Rechaza espacios, mayúsculas en segmentos estáticos o caracteres no válidos en URL y pide confirmación del nombre corregido.
- El resto de `$ARGUMENTS` es la descripción del contenido.

## 2. Cargar contexto y skills

1. Carga `core:project-context`; lee `CLAUDE.md`, `package.json` y `next.config.*`.
2. Carga `frontend:nextjs-app-router` y lee su `references/file-conventions.md`. Si la página carga datos cacheables, lee también `references/caching-by-version.md`.
3. Confirma que es un proyecto App Router (existe `app/` o `src/app/`). Si solo hay `pages/`, detente y pregunta si se quiere crear en Pages Router o migrar.
4. Anota la versión de `next` y si `cacheComponents` está activo: determina el tipado de `params`, las props de `error.tsx` y la estrategia de caché.

## 3. Detectar convenciones y conflictos

1. Lista las rutas existentes: `python3 "<carpeta de la skill nextjs-app-router>/scripts/list-routes.py" .`
2. Comprueba que la URL resultante (ignorando route groups) **no existe ya** ni colisiona con otra ruta de otro grupo. Si existe, detente e informa.
3. Revisa 1–2 páginas similares: layout que la envolverá, patrón de data fetching (data layer en `src/lib`), componentes UI, estilo de `loading`/`error` existentes, uso de auth (`requireUser`, `auth()`), i18n.
4. Revisa el root layout para conocer el `title.template` de metadata.

## 4. Crear los archivos

En `app/<ruta>/` (o `src/app/<ruta>/`):

- **`page.tsx`** (Server Component):
  - Si la ruta es dinámica: `export default async function Page(props: PageProps<'/<url>'>)` con `const { param } = await props.params` (Next 15.5+). En 15.0–15.4 tipa `{ params: Promise<{ param: string }> }`; en 14, objeto síncrono.
  - Carga datos llamando al data layer directamente (sin fetch a `/api` propio); `notFound()` si el recurso no existe.
  - Si la ruta es privada, verifica sesión/autorización con el helper del proyecto.
  - Con `cacheComponents`: runtime data dentro de `<Suspense>`; datos compartidos en funciones `'use cache'` + `cacheLife`.
- **`metadata`**: `export const metadata: Metadata` si es estática; `generateMetadata` si depende de params/datos (compartiendo la función de datos envuelta en `cache` de React para no duplicar la petición).
- **`loading.tsx`**: skeleton coherente con el layout, con `role="status"` o texto accesible.
- **`error.tsx`**: `'use client'`; props `{ error, retry }` en Next 16.3+, `{ error, unstable_retry }` en 16.2, `{ error, reset }` en versiones anteriores. Registra el error con el reporter del proyecto si existe; botón de reintento accesible.
- **`not-found.tsx`**: solo si la ruta es dinámica o llama a `notFound()`.
- **`generateStaticParams`**: solo si la descripción indica contenido conocido en build (blog, docs).
- Componentes específicos de la página en `_components/` junto a la ruta; `'use client'` solo en los interactivos.

Si la página necesita un formulario o mutación, crea `actions.ts` con `'use server'`, validación zod, autorización e invalidación de caché según la versión (ver skill).

## 5. Tests

Carga `frontend:frontend-testing` y sigue la convención del proyecto:
- Si la página es síncrona o su lógica está en funciones/componentes cliente, añade tests unitarios/RTL.
- Si hay Playwright configurado y la página es un flujo relevante, añade un e2e básico (navega, verifica heading por rol).
- No introduzcas un runner nuevo si el proyecto no tiene tests; menciónalo en la entrega.

## 6. Verificar

Con el gestor de paquetes del proyecto, corrige hasta que pasen:

1. Typecheck (`typecheck` o `npx tsc --noEmit`). Si usa `PageProps`, puede requerir `npx next typegen` antes para generar los tipos.
2. Lint de los archivos nuevos (`npx eslint <archivos>`; en Next 16 `next lint` ya no existe).
3. Tests relacionados.
4. Si la ruta usa caché, `generateStaticParams` o `cacheComponents`, ejecuta `next build` para detectar errores de prerender (avisa si tarda demasiado para correrlo).

## 7. Entregar

Responde con: URL final, árbol de archivos creados, cómo se obtienen los datos y la estrategia de caché elegida, metadata definida y resultado de cada verificación. Señala supuestos (auth, fuente de datos) que el usuario deba confirmar.
