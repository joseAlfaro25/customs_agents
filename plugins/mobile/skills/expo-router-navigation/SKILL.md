---
name: expo-router-navigation
description: "Navegación con Expo Router: estructura de app/, _layout, stacks, tabs, grupos, rutas dinámicas y tipadas, parámetros, modales, deep links y rutas protegidas por auth. Usar al crear pantallas, reorganizar rutas o depurar navegación y enlaces."
---

# expo-router-navigation

## Objetivo
Diseñar e implementar la navegación de una app Expo con routing basado en archivos, tipado de extremo a extremo y flujos de autenticación y deep links robustos.

## Cuándo aplicarla
- Añadir, mover o renombrar pantallas; crear stacks, tabs o modales.
- Pasar y leer parámetros entre pantallas.
- Proteger rutas por sesión/rol.
- Configurar deep links, universal links / App Links o `+not-found`.

Complementos: `mobile:react-native-components` (UI de la pantalla), `mobile:mobile-state-data` (sesión y datos), `mobile:mobile-testing` (tests con `renderRouter`). Si está instalado, `expo:expo-router` cubre en detalle headers nativos, toolbars, Link previews y NativeTabs.

## Paso 0: detectar
1. Versión de `expo` y `expo-router` en `package.json` (algunas APIs dependen del SDK; p. ej. `Stack.Protected` desde SDK 53, NativeTabs estable solo en SDKs recientes).
2. ¿Rutas en `app/` o en `src/app/`? Los proyectos nuevos usan `src/app`; respeta el existente.
3. ¿`experiments.typedRoutes: true` en app config? Si no, propón activarlo.
4. `scheme` en app config (necesario para deep links).
5. Revisa los `_layout.tsx` existentes para entender la jerarquía antes de añadir nada.

## Estructura de referencia
```
src/app/
  _layout.tsx                 # Root: providers + Stack raíz + guards de auth
  +not-found.tsx              # 404
  +native-intent.tsx          # (opcional) reescritura de deep links entrantes
  sign-in.tsx                 # pública
  (app)/                      # grupo protegido (no aparece en la URL)
    _layout.tsx               # Stack interno
    (tabs)/
      _layout.tsx             # Tabs
      index.tsx               # /
      orders/
        _layout.tsx           # Stack de la pestaña (mantiene historial por tab)
        index.tsx             # /orders
        [orderId].tsx         # /orders/123
      profile.tsx             # /profile
    settings/
      index.tsx               # /settings
    new-order.tsx             # presentado como modal desde (app)/_layout
```
Reglas:
- **Solo rutas en `app/`**. Componentes, hooks y lógica viven en `features/`, `components/`, `lib/` (fuera de `app/`), si no Expo Router los tratará como rutas.
- Cada archivo de ruta hace `export default` de un componente.
- Grupos `(nombre)` para organizar y compartir layouts sin afectar la URL.
- `index.tsx` es la ruta por defecto del directorio.
- Nombres de archivo en `kebab-case`; params dinámicos en `camelCase` (`[orderId].tsx`).

## Root layout
```tsx
// src/app/_layout.tsx
import { useEffect } from 'react';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { AppProviders } from '@/providers/AppProviders';
import { useSession } from '@/features/auth/useSession';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  return (
    <AppProviders>
      <RootNavigator />
    </AppProviders>
  );
}

function RootNavigator() {
  const { session, isLoading } = useSession();

  useEffect(() => {
    if (!isLoading) SplashScreen.hideAsync();
  }, [isLoading]);

  if (isLoading) return null; // el splash sigue visible

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={!!session}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
      <Stack.Protected guard={!session}>
        <Stack.Screen name="sign-in" />
      </Stack.Protected>
    </Stack>
  );
}
```
- `AppProviders` agrupa `GestureHandlerRootView`, `SafeAreaProvider` (si hace falta), `QueryClientProvider`, tema, `KeyboardProvider`, etc.
- Con `Stack.Protected`, cuando `guard` pasa a `false` el usuario es redirigido y se elimina el historial de esas rutas; los deep links a rutas protegidas acaban en la ruta disponible (anchor o primera pantalla). En SDKs recientes existe `redirectTo` en `Stack.Protected`; verifica tu versión.
- SDK < 53: usa `<Redirect href="/sign-in" />` en el layout del grupo protegido.

## Stacks
```tsx
// src/app/(app)/_layout.tsx
import { Stack } from 'expo-router';

export const unstable_settings = { anchor: '(tabs)' };

export default function AppLayout() {
  return (
    <Stack>
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="new-order" options={{ presentation: 'modal', title: 'Nuevo pedido' }} />
      <Stack.Screen name="settings/index" options={{ title: 'Ajustes' }} />
    </Stack>
  );
}
```
- `unstable_settings.anchor` define la pantalla base del stack (para que haya "atrás" al entrar por deep link). `initialRouteName` está deprecado en favor de `anchor`.
- Opciones dinámicas desde la pantalla: `<Stack.Screen options={{ title: order.code }} />` dentro del componente.
- Declara en el layout solo las pantallas que necesitan opciones; las demás se registran solas.

## Tabs
```tsx
// src/app/(app)/(tabs)/_layout.tsx
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ headerShown: false }}>
      <Tabs.Screen name="index" options={{ title: 'Inicio', tabBarIcon: ({ color, size }) => <Ionicons name="home" color={color} size={size} /> }} />
      <Tabs.Screen name="orders" options={{ title: 'Pedidos', tabBarIcon: ({ color, size }) => <Ionicons name="list" color={color} size={size} /> }} />
      <Tabs.Screen name="profile" options={{ title: 'Perfil', tabBarIcon: ({ color, size }) => <Ionicons name="person" color={color} size={size} /> }} />
    </Tabs>
  );
}
```
- Cada tab con navegación interna tiene su propia carpeta con `_layout.tsx` (Stack) para conservar el historial por pestaña.
- Tabs nativas (`NativeTabs`): import `expo-router/unstable-native-tabs` en SDK 54–57 y `expo-router/native-tabs` en SDKs posteriores. Úsalas si el proyecto busca UI 100% nativa; no son un reemplazo 1:1 de `Tabs` (menos personalización).
- Ocultar una ruta de la barra: `options={{ href: null }}`.

## Rutas dinámicas y parámetros
```tsx
// src/app/(app)/(tabs)/orders/[orderId].tsx
import { Stack, useLocalSearchParams } from 'expo-router';

export default function OrderDetailScreen() {
  const { orderId } = useLocalSearchParams<{ orderId: string }>();
  const { data, isPending, isError, refetch } = useOrder(orderId);
  // ...
}
```
- `useLocalSearchParams` (params de esta ruta) por defecto; `useGlobalSearchParams` solo si necesitas reaccionar a cambios de URL globales (re-renderiza más).
- Los params llegan como `string | string[]`: valida y convierte (`Number(page)`, Zod) antes de usarlos. Nunca confíes en ellos: pueden venir de un deep link.
- Pasa **ids**, no objetos completos: la pantalla destino carga los datos (TanStack Query los tendrá en caché).
- Catch-all: `[...slug].tsx` → `slug: string[]`.

## Navegar (tipado)
```tsx
import { Link, router } from 'expo-router';

<Link href={{ pathname: '/orders/[orderId]', params: { orderId: order.id } }} asChild>
  <Pressable accessibilityRole="link">...</Pressable>
</Link>

router.push('/new-order');
router.replace('/sign-in');      // sin volver atrás
router.back();
router.dismiss();                // cierra el modal
router.setParams({ filter: 'open' });
```
- Con `typedRoutes` activo, los `href` inválidos fallan en `tsc`. Los tipos se generan en `.expo/types` al ejecutar `npx expo start` (el `tsconfig.json` debe incluir `.expo/types/**/*.ts` y `expo-env.d.ts`); si `tsc` no los encuentra, arranca el dev server una vez.
- Typed routes solo admite rutas absolutas.
- `push` apila; `navigate` reutiliza si ya existe en el stack; `replace` sustituye.
- Tras login/logout no navegues manualmente si usas `Stack.Protected`: cambia la sesión y el guard redirige.

## Modales y sheets
- `presentation: 'modal'` en el `Stack.Screen` del layout padre.
- Sheets nativos: `presentation: 'formSheet'` con `sheetAllowedDetents` (p. ej. `[0.5, 1]`) y `sheetGrabberVisible`.
- Un modal con varios pasos: haz del modal una carpeta con su propio `_layout.tsx` (Stack).
- Siempre ofrece forma accesible de cerrar (botón con label), no solo el gesto.

## Hooks útiles
- `useFocusEffect(useCallback(() => { ...; return cleanup; }, []))`: efectos al enfocar la pantalla (refrescar, `BackHandler`).
- `usePathname()`, `useSegments()`: ubicación actual (analytics, lógica por grupo).
- `useNavigation()`: acceso al navigator de React Navigation cuando Expo Router no expone algo.

## Deep links y auth avanzada
Lee `references/deep-links-auth.md` cuando configures `scheme`, universal links / App Links, `+native-intent.tsx`, redirección tras login a la ruta original o protección por rol.

## Antipatrones
- Poner componentes, hooks o utilidades dentro de `app/`.
- Pasar objetos grandes o funciones por params.
- `router.push` dentro del render o sin guardas en `useEffect` (bucles de navegación).
- Redirigir en cada pantalla protegida en vez de centralizar el guard en el layout.
- Usar `useGlobalSearchParams` por defecto.
- Hardcodear strings de ruta sin `typedRoutes` en proyectos grandes.
- Duplicar headers custom cuando el Stack nativo ya ofrece `title`, `headerRight`, `headerSearchBarOptions`.

## Checklist final
- [ ] Archivo en la carpeta/grupo correcto; `export default` en la ruta.
- [ ] Layout nuevo solo si hace falta (stack propio, tabs, modal multi-paso).
- [ ] Params tipados y validados; se pasan ids.
- [ ] Links tipados (`tsc` sin errores con `typedRoutes`).
- [ ] Rutas privadas cubiertas por el guard; deep link a ruta privada sin sesión termina en login.
- [ ] Botón atrás/gesto funciona en iOS y Android; deep link directo tiene "atrás" (anchor).
- [ ] Test de navegación con `renderRouter` si la lógica es no trivial (`mobile:mobile-testing`).
