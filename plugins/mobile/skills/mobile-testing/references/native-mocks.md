# Mocks de módulos nativos para Jest (jest-expo)

Léelo al configurar `jest.setup.ts` o cuando un test falle con errores como `Cannot read property 'X' of undefined` en un módulo nativo, `NativeModule ... is null` o `TurboModuleRegistry.getEnforcing(...)`.

**Antes de copiar un mock**, comprueba que el paquete está instalado y su versión: varias librerías traen su propio mock oficial y la ruta puede cambiar entre majors. Incluye solo los mocks de paquetes que el proyecto usa.

## jest.config.js (piezas adicionales)
```js
module.exports = {
  preset: 'jest-expo',
  setupFiles: ['react-native-gesture-handler/jestSetup.js'],   // si usa Gesture Handler
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  // resolver: 'react-native-reanimated/jest/resolver',        // Reanimated 4: recomendado por su guía de testing
  transformIgnorePatterns: [
    // una sola regex; añade aquí paquetes ESM extra con |
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@sentry/react-native|native-base|react-native-svg|@shopify/flash-list)',
  ],
};
```
Si ya hay una clave `jest` en `package.json`, edítala allí en lugar de crear `jest.config.js` (Jest falla si hay dos configuraciones).

## jest.setup.ts
```ts
// --- Reanimated ---
require('react-native-reanimated').setUpTests();

// --- Safe area ---
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

// --- AsyncStorage (mock oficial) ---
jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock'),
);

// --- NetInfo (mock oficial) ---
jest.mock('@react-native-community/netinfo', () => require('@react-native-community/netinfo/jest/netinfo-mock.js'));

// --- expo-secure-store: almacén en memoria ---
jest.mock('expo-secure-store', () => {
  const store = new Map<string, string>();
  return {
    getItemAsync: jest.fn(async (k: string) => store.get(k) ?? null),
    setItemAsync: jest.fn(async (k: string, v: string) => void store.set(k, v)),
    deleteItemAsync: jest.fn(async (k: string) => void store.delete(k)),
    __reset: () => store.clear(),
  };
});

// --- expo-haptics ---
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  selectionAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium', Heavy: 'heavy' },
  NotificationFeedbackType: { Success: 'success', Warning: 'warning', Error: 'error' },
}));

// --- Silenciar ruido conocido (con moderación) ---
// jest.spyOn(console, 'warn').mockImplementation(() => {});
```

## MMKV
- Comprueba en la documentación de la versión instalada si `react-native-mmkv` se auto-mockea en Jest. Si no, mockea **tu wrapper** (`@/lib/storage`) en vez de la librería:
```ts
jest.mock('@/lib/storage', () => {
  const m = new Map<string, string>();
  return {
    kv: {
      getString: (k: string) => m.get(k),
      set: (k: string, v: string) => void m.set(k, v),
      remove: (k: string) => void m.delete(k),
      clearAll: () => m.clear(),
    },
  };
});
```
Tener un wrapper propio es precisamente lo que hace fácil este mock.

## expo-router (componentes que solo navegan)
```ts
const mockPush = jest.fn();
const mockBack = jest.fn();

jest.mock('expo-router', () => {
  const actual = jest.requireActual('expo-router');
  return {
    ...actual,
    router: { ...actual.router, push: (...a: unknown[]) => mockPush(...a), back: () => mockBack() },
    useRouter: () => ({ push: mockPush, back: mockBack, replace: jest.fn() }),
    useLocalSearchParams: jest.fn(() => ({ orderId: '1' })),
  };
});
```
Las variables usadas dentro de `jest.mock` deben empezar por `mock` (restricción de babel-jest). Para flujos de navegación reales usa `renderRouter` de `expo-router/testing-library`.

## Permisos (cámara, ubicación, notificaciones)
```ts
jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn(async () => ({ status: 'granted', granted: true, canAskAgain: true, expires: 'never' })),
  getCurrentPositionAsync: jest.fn(async () => ({ coords: { latitude: 4.6, longitude: -74.08, accuracy: 5 } })),
}));
```
Cubre ambos caminos: `granted` y `denied` (con `mockResolvedValueOnce`).

## expo-image
- Normalmente funciona con el mock de `jest-expo`. Si falla, `jest.mock('expo-image', () => ({ Image: 'Image' }))` para renderizar un host component simple.

## Gesture Handler
- `setupFiles: ['react-native-gesture-handler/jestSetup.js']`.
- Utilidades: `fireGestureHandler` y `getByGestureTestId` (y `createGestureController` en versiones recientes) desde `react-native-gesture-handler/jest-utils`; asigna `testID` al gesto. Verifica los nombres en la doc de tu versión.

## Variables de entorno en tests
- `process.env.EXPO_PUBLIC_API_URL` no se inlinea igual en Jest: defínela en `jest.setup.ts` (`process.env.EXPO_PUBLIC_API_URL = 'http://test.local'`) **antes** de importar `@/lib/env`, o mockea `@/lib/env`.

## fetch
```ts
const mockFetch = jest.spyOn(global, 'fetch');
mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({ id: '1' }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
```
Restaura con `mockFetch.mockRestore()` en `afterEach`, o usa MSW para un enfoque declarativo.

## Reset entre tests
```ts
afterEach(() => {
  jest.clearAllMocks();
  (require('expo-secure-store') as { __reset: () => void }).__reset();
});
```

## Errores frecuentes
| Error | Causa probable | Solución |
|---|---|---|
| `SyntaxError: Unexpected token 'export'` | Paquete ESM no transformado | Añádelo a `transformIgnorePatterns` |
| `Invariant Violation: TurboModuleRegistry.getEnforcing(...)` | Módulo nativo sin mock | Mock oficial o manual |
| `The module factory of jest.mock() is not allowed to reference any out-of-scope variables` | Variable sin prefijo `mock` | Renómbrala `mockX` |
| Warnings `not wrapped in act(...)` | Falta `await` (RNTL v14) o `findBy`/`waitFor` | Espera el estado final |
| Test pasa solo aislado | Estado compartido (store, QueryClient, mocks) | Resetea en `afterEach` |
