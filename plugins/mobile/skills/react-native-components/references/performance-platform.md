# Rendimiento y diferencias iOS/Android

Léelo al optimizar una pantalla lenta, al revisar código (lo usa `mobile:mobile-reviewer`) o cuando algo se ve/comporta distinto entre plataformas.

## Cómo medir
- Mide siempre en **build release o preview** (`npx expo run:ios --configuration Release`, `npx expo run:android --variant release` o un build de EAS con perfil `preview`). El modo dev añade mucho overhead.
- React DevTools (desde el menú de Expo CLI, tecla `j`) → Profiler: qué componentes re-renderizan y por qué.
- Perf Monitor del Dev Menu: FPS del hilo JS y UI. Hilo JS bajo = trabajo en React; hilo UI bajo = layout/animación/renderizado nativo.
- Android: Android Studio Profiler; iOS: Instruments (Time Profiler, Allocations).
- Tiempo de arranque: reduce trabajo en el root layout, difiere inicializaciones con `InteractionManager` o tras el primer render, mantén `expo-splash-screen` visible solo mientras cargas lo imprescindible (fuentes, sesión).

## Checklist de rendimiento
- [ ] Listas virtualizadas (`FlatList`/`FlashList`), nunca `ScrollView` + `map` con datos ilimitados.
- [ ] `renderItem` estable, items con `memo`, sin estilos/closures inline costosos.
- [ ] `keyExtractor` estable; sin `key` en el árbol de items con FlashList.
- [ ] Imágenes con `expo-image`, tamaño adecuado, `recyclingKey` en listas.
- [ ] Estado global con selectores (Zustand `useStore((s) => s.x)`), no el store entero.
- [ ] TanStack Query con `select` para derivar datos y evitar re-renders.
- [ ] Context con valores memoizados; contextos divididos si cambian con frecuencia distinta.
- [ ] Animaciones en el hilo UI (Reanimated), animando `transform`/`opacity`.
- [ ] Sin `console.log` en producción (`babel-plugin-transform-remove-console` o logger condicionado a `__DEV__`).
- [ ] Sin trabajo síncrono pesado en render (parseo de JSON grande, ordenaciones de miles de elementos sin `useMemo`).
- [ ] Bundles: evita importar librerías enteras (`lodash` completo, iconos completos); usa imports por ruta.
- [ ] Hermes activo (por defecto en Expo); no lo desactives.

## Diferencias iOS / Android

| Tema | iOS | Android | Qué hacer |
|---|---|---|---|
| Safe area | Notch / Dynamic Island / home indicator | Status bar + barra de navegación/gestos, edge-to-edge | `react-native-safe-area-context` siempre; nunca paddings fijos |
| Sombras | `shadowColor/Offset/Opacity/Radius` | `elevation` | `Platform.select` o `boxShadow` (RN reciente, New Architecture) |
| Teclado | Tapa el contenido; `KeyboardAvoidingView behavior="padding"` | `softwareKeyboardLayoutMode` (`resize`/`pan`) | `react-native-keyboard-controller` para formularios complejos |
| Botón atrás | Swipe desde el borde | Botón/gesto de sistema | Navigator lo gestiona; custom con `BackHandler` en `useFocusEffect` |
| Feedback táctil | Opacidad/escala | Ripple | `android_ripple` en `Pressable` |
| Fuentes | San Francisco; pesos por `fontWeight` | Roboto; con fuentes custom, `fontWeight` puede no mapear | Carga cada peso con `expo-font` y usa `fontFamily` explícito |
| Texto | `lineHeight` estable | Padding extra de fuente | `includeFontPadding: false` (Android) si el diseño lo exige |
| Permisos | Texto de uso obligatorio en Info.plist | Permisos en runtime y en AndroidManifest | Configurar vía `app.json` / config plugins (ver `mobile:expo-developer`) |
| Alert | 2–3 botones, estilo `destructive` | Máx. 3 botones, sin `destructive` visual | No dependas de estilos de `Alert` para UX crítica |
| Date/Time pickers | Inline/spinner | Diálogo | Probar ambos; considerar `@expo/ui` si el proyecto lo usa |
| Status bar | Estilo por pantalla | Translúcida con edge-to-edge | `expo-status-bar` con `style="auto"` |
| Deep links / universal links | Associated Domains | Intent filters / App Links | Ver `mobile:expo-router-navigation` |
| Overflow | `overflow: 'hidden'` recorta sombras | Igual, más `elevation` | Separa contenedor de sombra y contenedor recortado |

## Archivos por plataforma
- `Component.ios.tsx` / `Component.android.tsx` cuando el código diverge mucho; ambos deben exportar la misma API tipada.
- `Platform.OS === 'ios'` para diferencias pequeñas; `Platform.select({ ios, android, default })` para valores.
- Web (si el proyecto lo soporta): `.web.tsx` y no uses APIs nativas sin guardas.

## Pruebas manuales mínimas por plataforma
1. Dispositivo pequeño (iPhone SE / Android 5") y grande/tablet si aplica.
2. Fuente del sistema al máximo.
3. Modo oscuro.
4. VoiceOver (iOS) y TalkBack (Android) en el flujo tocado.
5. Rotación si la app no está bloqueada en portrait (`orientation` en app config).
6. Red lenta / sin red (ver `mobile:mobile-state-data`).
