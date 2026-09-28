# Animaciones y gestos (Reanimated + Gesture Handler)

Léelo cuando vayas a añadir o depurar una animación, un gesto o una transición. Verifica primero en `package.json` las versiones de `react-native-reanimated`, `react-native-worklets` y `react-native-gesture-handler`: las APIs cambian entre majors.

## Principios
1. **¿Debe animarse?** La animación comunica estado (aparece, se mueve, responde al dedo). Si no aporta, no la pongas.
2. **Hilo UI**: la lógica de animación corre en worklets en el hilo UI. No leas estado de React dentro de un worklet ni hagas `setState` directo: usa shared values y, para volver al hilo JS, `scheduleOnRN` (Reanimated 4 / `react-native-worklets`) o `runOnJS` (Reanimated 3; deprecado en 4).
3. **Propiedades baratas**: `transform` (translate, scale, rotate) y `opacity`. Evita animar `width`, `height`, `top`, `margin` en listas o gestos continuos.
4. **Spring para interacción, timing para cambios de estado sin dedo.**
5. **Reduce motion**: respeta la preferencia del sistema.

## Setup
- Expo: `npx expo install react-native-reanimated react-native-worklets react-native-gesture-handler`.
- `babel-preset-expo` ya incluye el plugin de worklets; no lo añadas manualmente salvo que el proyecto tenga un `babel.config.js` custom que lo necesite (en ese caso, `react-native-worklets/plugin` en v4 o `react-native-reanimated/plugin` en v3, **último** en la lista).
- `GestureHandlerRootView` envolviendo la app en el root `_layout.tsx`:

```tsx
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { Stack } from 'expo-router';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <Stack />
    </GestureHandlerRootView>
  );
}
```

## Animación básica
```tsx
import { useEffect } from 'react';
import Animated, { useSharedValue, useAnimatedStyle, withSpring, useReducedMotion } from 'react-native-reanimated';

export function ExpandableCard({ expanded }: { expanded: boolean }) {
  const reduceMotion = useReducedMotion();
  const progress = useSharedValue(expanded ? 1 : 0);

  useEffect(() => {
    progress.value = reduceMotion ? (expanded ? 1 : 0) : withSpring(expanded ? 1 : 0);
  }, [expanded, reduceMotion, progress]);

  const style = useAnimatedStyle(() => ({
    opacity: 0.6 + progress.value * 0.4,
    transform: [{ scale: 0.97 + progress.value * 0.03 }],
  }));

  return <Animated.View style={style}>{/* ... */}</Animated.View>;
}
```
- Nunca leas `progress.value` durante el render de React (solo en worklets/efectos).

## Layout animations (entrada/salida)
```tsx
import Animated, { FadeIn, FadeOut, LinearTransition } from 'react-native-reanimated';

<Animated.View entering={FadeIn.duration(200)} exiting={FadeOut} layout={LinearTransition}>
  ...
</Animated.View>
```
- Útiles para items que aparecen/desaparecen. En listas grandes, úsalas con moderación.
- Reanimated 4 también soporta animaciones y transiciones estilo CSS (`transitionProperty`, `animationName`) para casos declarativos simples; consulta la doc de la versión instalada.

## Gestos: Gesture Handler 3 (API de hooks)
```tsx
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, { useSharedValue, useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { scheduleOnRN } from 'react-native-worklets';

export function SwipeToDismiss({ onDismiss, children }: { onDismiss: () => void; children: React.ReactNode }) {
  const translateX = useSharedValue(0);

  const pan = usePanGesture({
    onUpdate: (e) => {
      translateX.value = e.translationX;
    },
    onDeactivate: (e) => {
      if (Math.abs(e.translationX) > 120) {
        scheduleOnRN(onDismiss);
      } else {
        translateX.value = withSpring(0);
      }
    },
  });

  const style = useAnimatedStyle(() => ({ transform: [{ translateX: translateX.value }] }));

  return (
    <GestureDetector gesture={pan}>
      <Animated.View style={style}>{children}</Animated.View>
    </GestureDetector>
  );
}
```
Cambios de nombre v2 → v3: `onStart` → `onActivate`, `onEnd` → `onDeactivate`, `onChange` se fusiona en `onUpdate`. El builder `Gesture.Pan()` sigue existiendo pero está deprecado en v3. Confirma nombres exactos en la doc de la versión instalada.

## Gestos: Gesture Handler 2 (builder)
```tsx
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { runOnJS } from 'react-native-reanimated'; // o scheduleOnRN si hay Reanimated 4

const pan = Gesture.Pan()
  .onUpdate((e) => {
    translateX.value = e.translationX;
  })
  .onEnd((e) => {
    if (Math.abs(e.translationX) > 120) runOnJS(onDismiss)();
    else translateX.value = withSpring(0);
  });
```
- Crea el gesto con `useMemo` si se construye en render y depende de props.

## Composición de gestos
- Simultáneos (pinch + rotate): composición simultánea (`Gesture.Simultaneous` en v2; en v3, el hook de composición equivalente, revisa la doc).
- Exclusivos (doble tap antes que tap): `Gesture.Exclusive(doubleTap, singleTap)` en v2.
- Gesto dentro de `ScrollView`: usa el `ScrollView`/`FlatList` exportado por `react-native-gesture-handler` o configura `simultaneousWithExternalGesture` para evitar conflictos.

## Feedback háptico
- `expo-haptics`: `Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light)` en confirmaciones y umbrales de gesto. No lo abuses.

## Bottom sheets y transiciones de pantalla
- Antes de instalar una librería de bottom sheet, considera `presentation: 'formSheet'` de Expo Router (nativo) o `@expo/ui` si el proyecto lo usa.
- Transiciones de pantalla: usa las opciones nativas del Stack (`animation: 'slide_from_right' | 'fade' | ...`) antes que animaciones JS custom.

## Depuración de jank
1. Reproduce en build release o dev build con perf monitor.
2. ¿Se re-renderiza el componente en cada frame? Mueve el valor a un shared value.
3. ¿Hay `scheduleOnRN`/`runOnJS` en `onUpdate`? Evítalo en cada frame.
4. ¿Se animan propiedades de layout en muchos elementos? Cambia a `transform`.
