# Setup de testing: Vitest, Jest, MSW y Playwright

Lee este archivo solo cuando el proyecto no tenga configurado el runner o haya que añadir MSW/Playwright. Instala con el gestor de paquetes del proyecto (detecta el lockfile: `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`, `package-lock.json`).

## Vitest (recomendado para Vite y Next.js)

Requisitos Vitest 5: Node ≥ 22.12 y Vite ≥ 6.4. Si el proyecto está en Node 20, usa Vitest 4.

```bash
npm i -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/dom \
  @testing-library/user-event @testing-library/jest-dom vite-tsconfig-paths
```

```ts
// vitest.config.mts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**'],
    css: false,
  },
})
```

```ts
// vitest.setup.ts
import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import { server } from './src/test/msw/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
})
afterAll(() => server.close())
```

- `cleanup()` explícito es necesario si no activas `globals: true`.
- Con `globals: true`, añade `"types": ["vitest/globals"]` al tsconfig.
- Alternativa a jsdom: `happy-dom` (más rápido, menos completo) o Browser Mode (estable desde Vitest 4) con `@vitest/browser` + Playwright para tests en navegador real.
- Scripts: `"test": "vitest"`, `"test:run": "vitest run"`, `"coverage": "vitest run --coverage"` (`@vitest/coverage-v8`).

## Jest (si el proyecto ya lo usa)

```bash
npm i -D jest jest-environment-jsdom @testing-library/react @testing-library/dom \
  @testing-library/user-event @testing-library/jest-dom @types/jest ts-node
```

```ts
// jest.config.ts (Next.js)
import type { Config } from 'jest'
import nextJest from 'next/jest.js'

const createJestConfig = nextJest({ dir: './' })

const config: Config = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  testPathIgnorePatterns: ['<rootDir>/e2e/'],
}

export default createJestConfig(config)
```

```ts
// jest.setup.ts
import '@testing-library/jest-dom'
```

- `next/jest` configura SWC, CSS/imágenes mockeadas y carga `.env`.
- Jest 30 requiere Node ≥ 18 y cambió algunos matchers/alias; revisa su guía de migración si actualizas desde 29.
- MSW 2 en Jest+jsdom puede necesitar polyfills (`TextEncoder`, `ReadableStream`, `fetch`) o `testEnvironment: 'jest-fixed-jsdom'`; consulta la sección de Jest en la doc de MSW.

## MSW 2

```bash
npm i -D msw
```

```ts
// src/test/msw/server.ts
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

```ts
// src/test/msw/handlers.ts
import { http, HttpResponse, delay } from 'msw'

export const handlers = [
  http.get('*/api/products', async () => {
    await delay(50)
    return HttpResponse.json([{ id: '1', name: 'Camiseta' }])
  }),
  http.post('*/api/products', async ({ request }) => {
    const body = (await request.json()) as { name: string }
    return HttpResponse.json({ id: '2', ...body }, { status: 201 })
  }),
]
```

- API v2: `http.get/post/...` + `HttpResponse.json()`; la v1 (`rest`, `res(ctx.json())`) ya no existe.
- Para desarrollo en navegador: `npx msw init public/ --save` y `setupWorker` de `msw/browser`.
- Reutiliza los mismos handlers en tests, Storybook y desarrollo.

## Playwright

```bash
npm init playwright@latest   # o: npm i -D @playwright/test && npx playwright install --with-deps
```

```ts
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test'

const PORT = Number(process.env.PORT ?? 3000)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    { name: 'chromium', use: { ...devices['Desktop Chrome'], storageState: 'e2e/.auth/user.json' }, dependencies: ['setup'] },
  ],
  webServer: {
    command: process.env.CI ? 'npm run build && npm run start' : 'npm run dev',
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
})
```

```ts
// e2e/auth.setup.ts
import { test as setup, expect } from '@playwright/test'

setup('autenticar', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill(process.env.E2E_USER!)
  await page.getByLabel('Contraseña').fill(process.env.E2E_PASSWORD!)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('navigation')).toBeVisible()
  await page.context().storageState({ path: 'e2e/.auth/user.json' })
})
```

- Añade `e2e/.auth/` a `.gitignore`.
- Si no hay login, elimina el proyecto `setup` y `storageState`.
- Debug: `npx playwright test --ui`, `--debug`, `npx playwright show-trace`.

## Scripts sugeridos

```json
{
  "scripts": {
    "test": "vitest",
    "test:run": "vitest run",
    "test:e2e": "playwright test",
    "typecheck": "tsc --noEmit"
  }
}
```
