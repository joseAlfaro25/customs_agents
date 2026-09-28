---
name: mobile-testing
description: "Testing en apps Expo/React Native: Jest con jest-expo, React Native Testing Library, mocks de módulos nativos, tests de navegación con expo-router y e2e con Maestro o Detox. Usar al escribir, configurar o arreglar tests de la app móvil."
---

# mobile-testing

## Objetivo
Tests que verifican comportamiento visible para el usuario (lo que ve y lo que toca), rápidos y estables, con mocks mínimos de lo nativo y e2e para los flujos críticos.

## Cuándo aplicarla
- Añadir tests a una pantalla, componente, hook o store.
- Configurar Jest en un proyecto Expo o arreglar errores de transformación/mocks.
- Probar navegación, auth o deep links.
- Montar e2e (Maestro/Detox) o depurar tests flaky.

La estrategia general (pirámide, qué testear) está en `core:testing-strategy`. Complementos: `mobile:mobile-state-data` (mocks de red/stores), `mobile:expo-router-navigation`.

## Paso 0: detectar
1. `package.json`: `jest`, `jest-expo`, `@testing-library/react-native` (versión), `msw`, `maestro`/`detox`. Script `test`.
2. Config de Jest (`jest.config.js` o clave `jest` en `package.json`) y archivo de setup (`jest.setup.ts`).
3. Convención de ubicación: `__tests__/` junto al código o `*.test.tsx` al lado. **Sigue la existente.**
4. Versión de RNTL: **v14 hace `render`, `fireEvent`, `renderHook`, `act`, `rerender` y `unmount` asíncronos (hay que hacer `await`)**; v13 y anteriores son síncronos. `userEvent` es asíncrono en ambas.

## Setup
```sh
npx expo install jest-expo jest @types/jest @testing-library/react-native --dev
```
```js
// jest.config.js
module.exports = {
  preset: 'jest-expo',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@sentry/react-native|native-base|react-native-svg)',
  ],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' }, // alinea con los paths de tsconfig
};
```
- Si una librería ESM falla con `SyntaxError: Unexpected token 'export'`, añádela al grupo de `transformIgnorePatterns`.
- `tsconfig.json`: `"types": ["jest"]` si hace falta.
- Los matchers de RNTL (`toBeOnTheScreen`, `toHaveTextContent`, `toBeDisabled`…) vienen incluidos en versiones actuales; en versiones antiguas, `import '@testing-library/react-native/extend-expect'` en el setup.
- Multiplataforma: `jest-expo/universal` ejecuta los tests en ios/android/web; úsalo solo si el proyecto lo necesita.

## Mocks de módulos nativos
`jest-expo` ya mockea la parte nativa de muchos módulos de Expo, pero devuelven valores vacíos: mockea explícitamente lo que tu test necesita. Lee `references/native-mocks.md` para el `jest.setup.ts` completo (SecureStore, AsyncStorage, MMKV, NetInfo, Reanimated, Gesture Handler, safe area, expo-router, expo-image, permisos, haptics).

Regla: mockea en el **borde** (módulo nativo, red), no tus propios hooks/componentes, salvo que el test sea explícitamente de integración parcial.

## Test de componente
```tsx
import { render, screen, userEvent } from '@testing-library/react-native';
import { Button } from '../Button';

describe('Button', () => {
  it('llama onPress al tocarlo', async () => {
    const onPress = jest.fn();
    const user = userEvent.setup();
    await render(<Button label="Guardar" onPress={onPress} />); // v14: await; v13: sin await (await es inocuo)

    await user.press(screen.getByRole('button', { name: 'Guardar' }));

    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('no responde cuando está cargando', async () => {
    await render(<Button label="Guardar" loading onPress={jest.fn()} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```
Prioridad de queries: `getByRole` (con `name`) → `getByLabelText` → `getByPlaceholderText` → `getByText` → `getByTestId` (último recurso). Si no puedes encontrar algo por rol o label, probablemente falta accesibilidad.
- `getBy*` para lo que debe estar; `queryBy*` para afirmar ausencia; `findBy*` para lo asíncrono.
- `userEvent` en vez de `fireEvent` para interacciones realistas (`press`, `type`, `clear`, `scrollTo`).
- Usa `screen`, no desestructures el resultado de `render`.

## Test de pantalla con datos (TanStack Query)
```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

jest.mock('@/features/orders/api/orders.api');
const mockedGetOrder = jest.mocked(getOrder);

it('muestra el pedido y maneja error', async () => {
  mockedGetOrder.mockResolvedValueOnce({ id: '1', code: 'A-1', status: 'paid', total: 10, createdAt: '2026-01-01' });
  await renderWithProviders(<OrderDetail orderId="1" />);
  expect(await screen.findByText('A-1')).toBeOnTheScreen();
});

it('muestra error con reintento', async () => {
  mockedGetOrder.mockRejectedValueOnce(new Error('boom'));
  await renderWithProviders(<OrderDetail orderId="1" />);
  expect(await screen.findByRole('button', { name: /reintentar/i })).toBeOnTheScreen();
});
```
- `QueryClient` nuevo por test (sin caché compartida) y `retry: false`.
- Alternativa realista: MSW (`msw/native`) interceptando `fetch`; requiere polyfills según versión, revisa su guía.
- Cubre siempre: carga, éxito, vacío y error.

## Tests de navegación (Expo Router)
```tsx
import { renderRouter, screen } from 'expo-router/testing-library';

it('navega del listado al detalle', async () => {
  await renderRouter(
    {
      '(tabs)/orders/index': OrdersScreen,
      '(tabs)/orders/[orderId]': OrderDetailScreen,
    },
    { initialUrl: '/orders' },
  );
  await userEvent.setup().press(await screen.findByText('A-1'));
  expect(screen).toHavePathname('/orders/1');
});
```
- Matchers: `toHavePathname`, `toHavePathnameWithParams`, `toHaveSegments`, `toHaveRouterState`.
- `renderRouter` también acepta una carpeta fixture o un array de nombres de ruta.
- Para componentes que solo usan `router.push`, basta con mockear `expo-router` (ver `references/native-mocks.md`).

## Hooks y stores
```ts
import { renderHook, act } from '@testing-library/react-native';

it('actualiza el tema', async () => {
  const { result } = await renderHook(() => usePreferences());
  await act(() => result.current.setTheme('dark'));
  expect(result.current.theme).toBe('dark');
});

afterEach(() => usePreferences.setState(usePreferences.getInitialState()));
```
- Resetea stores de Zustand entre tests.
- Timers: `jest.useFakeTimers()` con `userEvent.setup({ advanceTimers: jest.advanceTimersByTime })`.

## E2E
- **Maestro** (recomendado para empezar): flujos YAML, sin tocar código nativo, funciona con builds de EAS y en EAS Workflows.
- **Detox**: más control, grey-box, requiere prebuild y configuración nativa.
- Lee `references/e2e.md` para ejemplos de flujos, testIDs, CI y cuándo elegir cada uno.

## Antipatrones
- Snapshots grandes como único test (se aprueban sin mirar).
- Testear detalles de implementación (estado interno, nombres de funciones, número de renders).
- `getByTestId` para todo.
- `waitFor` con side effects dentro o sin `await`.
- Mockear el componente bajo test o sus hooks propios.
- Olvidar `await` con RNTL v14 (warnings de `act` y tests que pasan por accidente).
- `QueryClient` compartido entre tests.
- `setTimeout` reales en tests.

## Checklist final
- [ ] Tests junto a la convención del proyecto; nombres que describen comportamiento.
- [ ] Queries por rol/label; interacciones con `userEvent`.
- [ ] Estados de carga, error, vacío y éxito cubiertos en pantallas con datos.
- [ ] Mocks solo en bordes (nativo, red) y reseteados entre tests.
- [ ] `npx jest --ci` (o el script del proyecto) en verde, sin warnings de `act`.
- [ ] Flujos críticos (login, compra) cubiertos por e2e si el proyecto tiene Maestro/Detox.
