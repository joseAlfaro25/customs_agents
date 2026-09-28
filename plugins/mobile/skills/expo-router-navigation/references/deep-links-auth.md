# Deep links, universal links y auth avanzada

Léelo al configurar enlaces externos a la app, redirecciones tras login o protección por rol.

## 1. Scheme (custom URL)
```json
// app.json
{ "expo": { "scheme": "myapp" } }
```
- Con Expo Router, cada ruta es enlazable automáticamente: `myapp://orders/123` abre `app/.../orders/[orderId].tsx`.
- Probar:
  - iOS simulator: `npx uri-scheme open "myapp://orders/123" --ios` o `xcrun simctl openurl booted "myapp://orders/123"`.
  - Android: `adb shell am start -W -a android.intent.action.VIEW -d "myapp://orders/123"`.
- En Expo Go el scheme es `exp://...`; prueba los deep links reales en un dev build.
- Construir URLs: `Linking.createURL('/orders/123')` de `expo-linking` (respeta el entorno).

## 2. Universal links (iOS) y App Links (Android)
Necesitan dominio propio y archivos servidos por HTTPS.

```ts
// app.config.ts (fragmento)
ios: {
  associatedDomains: ['applinks:example.com'],
},
android: {
  intentFilters: [
    {
      action: 'VIEW',
      autoVerify: true,
      data: [{ scheme: 'https', host: 'example.com', pathPrefix: '/orders' }],
      category: ['BROWSABLE', 'DEFAULT'],
    },
  ],
},
```
- iOS: servir `https://example.com/.well-known/apple-app-site-association` (JSON, sin extensión, `Content-Type: application/json`) con el `appID` `TEAMID.bundleIdentifier`.
- Android: servir `https://example.com/.well-known/assetlinks.json` con el SHA-256 del certificado de firma (el de la Play Console si usas Play App Signing; `eas credentials` muestra el fingerprint del keystore de EAS).
- Estos cambios son nativos: requieren nuevo build (no llegan por EAS Update).
- Coordina con backend/devops (plugin `devops`/`backend`) el hosting de los archivos `.well-known`.

## 3. Reescribir enlaces entrantes: `+native-intent.tsx`
Para URLs de terceros (campañas, SDKs de atribución) o rutas antiguas que no mapean 1:1 con `app/`.

```ts
// src/app/+native-intent.tsx
export function redirectSystemPath({ path, initial }: { path: string; initial: boolean }) {
  try {
    const url = new URL(path, 'myapp://app.home');
    if (url.pathname.startsWith('/legacy/order/')) {
      return `/orders/${url.pathname.split('/').pop()}`;
    }
    return path;
  } catch {
    return '/';
  }
}
```
- Se ejecuta fuera del árbol de React: sin hooks ni contexto.
- `initial` es `true` cuando el enlace abrió la app desde cerrada.
- Nunca debe lanzar: ante error, devuelve una ruta segura. Puede devolver una `Promise<string>`.

## 4. Volver a la ruta original tras login
Con `Stack.Protected`, un deep link a una ruta privada sin sesión termina en la ruta pública disponible. Para retomar el destino:
1. Captura la URL entrante con `expo-linking` (`Linking.useLinkingURL()` / `Linking.getInitialURL()`), no con `usePathname()`: cuando el efecto corre, el guard ya pudo redirigir a `/sign-in`.
2. Si no hay sesión, guarda la ruta pendiente (store en memoria, p. ej. Zustand).
3. Tras `signIn()` exitoso, si hay ruta pendiente, `router.replace(pendingHref)` y límpiala.
4. Valida que la ruta pendiente sea interna (empiece por `/`, sin host externo) para evitar open redirects.

```tsx
import * as Linking from 'expo-linking';

const url = Linking.useLinkingURL();
const setPendingHref = useAuthStore((s) => s.setPendingHref);

useEffect(() => {
  if (!url || session || isLoading) return;
  const { path } = Linking.parse(url);
  if (path && path !== 'sign-in') setPendingHref(`/${path}`);
}, [url, session, isLoading, setPendingHref]);
```
Verifica el nombre del hook en tu versión de `expo-linking` (`useLinkingURL` en SDKs recientes; `useURL` en anteriores).

## 5. Protección por rol
Anida guards: el más externo por sesión, el interno por permiso.
```tsx
<Stack>
  <Stack.Protected guard={!!session}>
    <Stack.Screen name="(app)" />
    <Stack.Protected guard={session?.role === 'admin'}>
      <Stack.Screen name="admin" />
    </Stack.Protected>
  </Stack.Protected>
  <Stack.Protected guard={!session}>
    <Stack.Screen name="sign-in" />
  </Stack.Protected>
</Stack>
```
- `Tabs.Protected` existe análogamente para ocultar pestañas.
- La protección en cliente es UX, **no seguridad**: el backend (NestJS/FastAPI) debe validar el token y el rol en cada endpoint.

## 6. Sesión: fuente de verdad
- Token en `expo-secure-store` (nunca AsyncStorage). Ver `mobile:mobile-state-data`.
- `isLoading` mientras se lee el token al arrancar → mantén el splash (`expo-splash-screen`).
- Ante 401 del API: limpia token y estado → el guard redirige a login automáticamente.

## 7. OAuth / SSO
- `expo-auth-session` + `expo-web-browser` (`WebBrowser.maybeCompleteAuthSession()` en la pantalla de callback) para flujos OAuth/OIDC con PKCE.
- El `redirectUri` debe usar el scheme de la app (`AuthSession.makeRedirectUri()`), registrado en el proveedor.
- Proveedores gestionados (Clerk, Supabase, Firebase) tienen SDKs propios; sigue su guía para Expo.

## 8. Checklist de deep links
- [ ] `scheme` definido y único.
- [ ] Rutas enlazables validan params (pueden llegar valores arbitrarios).
- [ ] Deep link con app cerrada y abierta probado en iOS y Android.
- [ ] Deep link a ruta privada sin sesión → login → destino original.
- [ ] Universal/App Links verificados (archivos `.well-known` accesibles, fingerprint correcto).
- [ ] `+not-found.tsx` amigable con acción para volver al inicio.
