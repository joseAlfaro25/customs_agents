---
name: frontend-testing
description: "Testing frontend con Vitest o Jest, React Testing Library, user-event, MSW y Playwright, incluyendo Server Components y Server Actions de Next.js. Usar al escribir, arreglar o planificar tests de UI, hooks, formularios o flujos e2e."
---

# frontend-testing

Cómo testear UI React/Next.js con confianza y sin tests frágiles. Referencias: **Vitest 5** (sep 2026; 4.x sigue muy extendido), **Jest 30**, **React Testing Library 16**, **user-event 14**, **MSW 2**, **Playwright**. **Verifica runner y versiones en `package.json`** y usa el que ya tenga el proyecto; no introduzcas un segundo runner.

## Cuándo aplicarla

- Añadir tests a un componente, hook, formulario o página.
- Arreglar tests frágiles, lentos o con warnings de `act(...)`.
- Configurar Vitest/Jest, MSW o Playwright desde cero.
- Decidir qué nivel de test (unit, integración, e2e) cubre un cambio.

## Paso 0: detectar el setup

1. `package.json`: ¿`vitest` o `jest`? ¿`@testing-library/*`, `msw`, `@playwright/test`? Scripts `test`, `test:e2e`.
2. Config: `vitest.config.*`, `jest.config.*`, `playwright.config.*`, archivo de setup (`vitest.setup.ts`).
3. Convención de ubicación: `*.test.tsx` colocalizado o `__tests__/`; e2e en `e2e/` o `tests/`.
4. Utilidades existentes: `renderWithProviders`, factories, handlers de MSW.

Si falta configuración, usa las plantillas de [references/setup.md](references/setup.md).

## Qué testear (y dónde)

| Nivel | Herramienta | Qué cubre |
|---|---|---|
| Unit | Vitest/Jest | Funciones puras, schemas zod, hooks, reducers, Server Actions (como funciones) |
| Integración de componentes | RTL + user-event + MSW | Comportamiento visible: render, interacción, estados de carga/error/vacío |
| E2E | Playwright | Flujos críticos reales: login, checkout, navegación, async Server Components |

Prioriza tests de integración de componentes; e2e solo para los flujos de mayor valor. Enfoque general en `core:testing-strategy`.

Testea **comportamiento observable**, no implementación: lo que el usuario ve y hace, no estado interno, nombres de clases ni número de renders.

## React Testing Library

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { LoginForm } from './login-form'

describe('LoginForm', () => {
  it('envía las credenciales', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<LoginForm onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText(/email/i), 'ana@example.com')
    await user.type(screen.getByLabelText(/contraseña/i), 'secreto123')
    await user.click(screen.getByRole('button', { name: /entrar/i }))

    expect(onSubmit).toHaveBeenCalledWith({ email: 'ana@example.com', password: 'secreto123' })
  })

  it('muestra error si el email es inválido', async () => {
    const user = userEvent.setup()
    render(<LoginForm onSubmit={vi.fn()} />)

    await user.type(screen.getByLabelText(/email/i), 'no-es-email')
    await user.click(screen.getByRole('button', { name: /entrar/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/email inválido/i)
  })
})
```

Prioridad de queries (de mejor a peor):
1. `getByRole(role, { name })` — también valida accesibilidad.
2. `getByLabelText`, `getByPlaceholderText`, `getByText`, `getByDisplayValue`.
3. `getByAltText`, `getByTitle`.
4. `getByTestId` — último recurso.

Reglas:
- `getBy*` para lo que debe estar; `queryBy*` solo para afirmar ausencia; `findBy*` para lo que aparece de forma asíncrona.
- `userEvent.setup()` al inicio de cada test y `await` en cada interacción. No uses `fireEvent` salvo eventos que user-event no cubre.
- Usa `screen`, no desestructures `render`. Evita `container.querySelector`.
- `waitFor` solo para aserciones que esperan un cambio; nunca con efectos secundarios dentro.
- Matchers de `@testing-library/jest-dom`: `toBeInTheDocument`, `toHaveTextContent`, `toBeDisabled`, `toHaveAccessibleName`.
- Envuelve providers (tema, QueryClient, router, i18n) en un `renderWithProviders` compartido; nuevo `QueryClient` por test con `retry: false`.

## Hooks

```ts
import { renderHook, act } from '@testing-library/react'

it('incrementa', () => {
  const { result } = renderHook(() => useCounter(0))
  act(() => result.current.increment())
  expect(result.current.count).toBe(1)
})
```

Si el hook solo se usa en un componente, testéalo a través del componente.

## Mocking de red con MSW

Mockea en el borde de red, no los módulos de fetch:

```ts
// test/msw/handlers.ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/users/:id', ({ params }) =>
    HttpResponse.json({ id: params.id, name: 'Ana' }),
  ),
]
```

```ts
// en un test: sobrescribir para un caso de error
import { server } from '@/test/msw/server'

server.use(http.get('/api/users/:id', () => HttpResponse.json({ message: 'boom' }, { status: 500 })))
```

- `onUnhandledRequest: 'error'` para detectar peticiones no mockeadas.
- `server.resetHandlers()` en `afterEach`. Setup completo en [references/setup.md](references/setup.md).
- Mockea módulos (`vi.mock`) solo para dependencias no-red: `next/navigation`, `next/cache`, auth, fechas.

## Next.js: Server Components

- **Síncronos**: se renderizan con RTL como cualquier componente.
- **Async**: Vitest/Jest no los soportan oficialmente (la doc de Next recomienda e2e). Atajo aceptable para componentes hoja sin hijos async:

```tsx
it('muestra el post', async () => {
  vi.mocked(getPost).mockResolvedValue({ title: 'Hola', body: '...' })
  render(await PostPage({ params: Promise.resolve({ slug: 'hola' }), searchParams: Promise.resolve({}) }))
  expect(screen.getByRole('heading', { name: 'Hola' })).toBeInTheDocument()
})
```

  Si hay hijos async, `<Suspense>`, `cookies()` o `'use cache'`, testéalo con Playwright.
- Extrae la lógica (data access, transformaciones) a funciones puras y testéalas en unit.
- Mockea `next/navigation`:

```ts
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn(), back: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/dashboard',
  useSearchParams: () => new URLSearchParams(),
  redirect: vi.fn((url: string) => { throw new Error(`NEXT_REDIRECT:${url}`) }),
  notFound: vi.fn(() => { throw new Error('NEXT_NOT_FOUND') }),
}))
```

## Next.js: Server Actions

Son funciones async: testéalas directamente con `FormData`, mockeando auth, DB y `next/cache`.

```ts
import { beforeEach, expect, it, vi } from 'vitest'
import { createPost } from './actions'

vi.mock('next/cache', () => ({ updateTag: vi.fn(), revalidateTag: vi.fn(), revalidatePath: vi.fn() }))
vi.mock('next/navigation', () => ({ redirect: vi.fn() }))
vi.mock('@/lib/auth', () => ({ requireUser: vi.fn().mockResolvedValue({ id: 'u1' }) }))
vi.mock('@/lib/db', () => ({ db: { post: { create: vi.fn().mockResolvedValue({ id: 'p1' }) } } }))

function form(data: Record<string, string>) {
  const fd = new FormData()
  for (const [k, v] of Object.entries(data)) fd.set(k, v)
  return fd
}

it('devuelve errores de validación', async () => {
  const state = await createPost({}, form({ title: 'a', body: '' }))
  expect(state.errors?.title).toBeDefined()
})

it('crea, invalida y redirige', async () => {
  const { updateTag } = await import('next/cache')
  const { redirect } = await import('next/navigation')
  await createPost({}, form({ title: 'Título válido', body: 'Contenido' }))
  expect(updateTag).toHaveBeenCalledWith('posts')
  expect(redirect).toHaveBeenCalledWith('/posts/p1')
})
```

Testea también el caso no autorizado (`requireUser` rechaza). El flujo completo formulario → acción → UI actualizada va en e2e.

## Playwright (e2e)

```ts
import { expect, test } from '@playwright/test'

test('usuario crea un post', async ({ page }) => {
  await page.goto('/posts/new')
  await page.getByLabel('Título').fill('Mi post')
  await page.getByLabel('Contenido').fill('Hola mundo')
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page).toHaveURL(/\/posts\/\w+/)
  await expect(page.getByRole('heading', { name: 'Mi post' })).toBeVisible()
})
```

- Locators por rol/label/texto; aserciones web-first (`await expect(locator).toBeVisible()`), nunca `waitForTimeout`.
- Autenticación una vez con un setup project y `storageState`.
- Datos aislados por test (seed vía API o fixtures); tests independientes y paralelizables.
- Corre contra un build de producción (`next build && next start`) en CI vía `webServer`.
- Next 16.3+: `instant()` de `@next/playwright` para asegurar que una navegación muestra contenido inmediato.
- Accesibilidad automatizada: `@axe-core/playwright` en páginas clave si el proyecto lo usa.

## Antipatrones

- Testear detalles de implementación (estado interno, llamadas a `setState`, snapshots gigantes).
- `getByTestId` cuando existe un rol o label.
- `fireEvent` en lugar de user-event; olvidar `await` en interacciones.
- `waitFor(() => expect(...))` para algo que `findBy*` resuelve.
- Mockear `fetch` a mano en cada test en lugar de MSW.
- Tests que dependen del orden o comparten estado (mocks no reseteados; en Vitest 5 `clearMocks` es `true` por defecto, en 4.x no).
- `sleep`/timeouts fijos en e2e.
- Ignorar warnings de `act(...)`: suelen indicar una actualización asíncrona sin esperar.

## Checklist final

- [ ] Runner y convenciones del proyecto respetados.
- [ ] Queries por rol/label; interacciones con user-event y `await`.
- [ ] Casos: éxito, error, vacío/carga y validación cuando aplican.
- [ ] Red mockeada con MSW; sin peticiones no manejadas.
- [ ] Async Server Components y flujos críticos cubiertos con Playwright.
- [ ] Tests deterministas (fechas/aleatoriedad controladas con `vi.useFakeTimers`/`vi.setSystemTime`).
- [ ] La suite pasa en local y en modo CI (`vitest run`, `jest --ci`, `playwright test`).

## Skills relacionadas

- `core:testing-strategy` para la estrategia general y pirámide de tests.
- `frontend:react-components` para entender el componente bajo test.
- `frontend:nextjs-app-router` para Server Components, Actions y caché.
