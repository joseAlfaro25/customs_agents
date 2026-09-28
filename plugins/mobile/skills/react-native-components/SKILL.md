---
name: react-native-components
description: "Patrones de componentes React Native + Expo con TypeScript: estructura por feature, estilos, listas, safe areas, teclado, imágenes, gestos, animaciones, accesibilidad e iOS/Android. Usar al crear, refactorizar u optimizar pantallas y componentes."
---

# react-native-components

## Objetivo
Construir componentes y pantallas React Native tipados, accesibles, rápidos y consistentes con el proyecto, usando las librerías estándar del ecosistema Expo (New Architecture por defecto).

## Cuándo aplicarla
- Crear o refactorizar un componente, pantalla o lista.
- Resolver problemas de layout (safe area, teclado, notch, edge-to-edge en Android).
- Añadir gestos, animaciones o imágenes.
- Optimizar rendimiento (re-renders, listas lentas, animaciones con jank).

Para routing usa `mobile:expo-router-navigation`; para datos `mobile:mobile-state-data`; para tipos avanzados `frontend:typescript-patterns`. Si está instalado el plugin oficial `expo`, `expo:expo-native-ui`, `expo:expo-animation` y `expo:expo-ui` son complementos útiles.

## Paso 0: detectar antes de escribir
1. Lee `package.json`: versión de `expo`, `react-native`, `react`. **No asumas versiones**: la API de varias librerías cambió entre majors.
2. Estilos: ¿hay `nativewind` + `tailwind.config.js` / `global.css`? ¿`StyleSheet`? ¿Unistyles/Tamagui/Restyle? **Sigue lo que ya usa el proyecto**; no mezcles sistemas.
3. ¿Existe carpeta de UI compartida (`components/ui`, `src/components`) y tokens (`theme.ts`, `constants/Colors.ts`)? Reutiliza antes de crear.
4. Versiones instaladas de `react-native-reanimated`, `react-native-gesture-handler`, `@shopify/flash-list`, `expo-image`, `react-native-keyboard-controller`.

## Estructura por feature
```
src/
  app/                    # rutas de Expo Router (o app/ en la raíz; respeta la existente)
  features/
    orders/
      components/         # OrderCard.tsx, OrderList.tsx (solo de esta feature)
      hooks/              # useOrders.ts
      api/                # orders.api.ts, orders.schemas.ts
      types.ts
      index.ts            # API pública de la feature (opcional)
  components/
    ui/                   # Button, Text, Card, Screen... (design system)
  theme/                  # tokens: colors, spacing, typography
  lib/                    # clientes, utilidades sin UI
```
- Las rutas en `app/` son **delgadas**: leen params, llaman hooks y componen componentes de `features/`.
- Un componente por archivo, `PascalCase.tsx`; hooks `useXxx.ts`.
- Una feature no importa internos de otra: si se comparte, sube a `components/` o `lib/`.

## Componentes tipados
```tsx
import { Pressable, Text, StyleSheet, type PressableProps } from 'react-native';

type ButtonVariant = 'primary' | 'secondary';

export type ButtonProps = Omit<PressableProps, 'children' | 'style'> & {
  label: string;
  variant?: ButtonVariant;
  loading?: boolean;
};

export function Button({ label, variant = 'primary', loading = false, disabled, ...rest }: ButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: isDisabled, busy: loading }}
      disabled={isDisabled}
      hitSlop={8}
      style={({ pressed }) => [styles.base, styles[variant], pressed && styles.pressed, isDisabled && styles.disabled]}
      {...rest}
    >
      <Text style={styles.label}>{loading ? 'Cargando…' : label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: { minHeight: 48, paddingHorizontal: 16, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  primary: { backgroundColor: '#2563eb' },
  secondary: { backgroundColor: '#e5e7eb' },
  pressed: { opacity: 0.85 },
  disabled: { opacity: 0.5 },
  label: { fontSize: 16, fontWeight: '600', color: '#fff' },
});
```
Reglas:
- Props como `type` exportado; extiende props nativas (`PressableProps`, `TextInputProps`, `ViewProps`) con `Omit` en vez de redefinirlas.
- Named exports para componentes; `export default` solo en archivos de ruta (Expo Router lo exige).
- Sin `any`. Callbacks tipados (`onSelect: (id: string) => void`).
- Usa `Pressable`, no `TouchableOpacity` en código nuevo.
- Colores/espaciados desde tokens del tema, no literales repetidos (el ejemplo usa literales por brevedad).

## Estilos: StyleSheet vs NativeWind
| Si el proyecto usa… | Haz |
|---|---|
| `StyleSheet` | `StyleSheet.create` al final del archivo; estilos dinámicos como array `[styles.a, cond && styles.b]`. |
| NativeWind | `className` con tokens de `tailwind.config`; `cn()`/`clsx` para condicionales si existe; no metas `style` inline salvo valores animados. |
| Ambos | Respeta el que domina en la carpeta que tocas. |

- Nunca crees objetos de estilo inline en listas grandes (`style={{...}}` en `renderItem`).
- Dark mode: `useColorScheme()` o el mecanismo del tema existente; nada de colores duros que rompan en oscuro.
- Tamaños de texto: respeta Dynamic Type/escala de fuente; no pongas `allowFontScaling={false}` salvo casos justificados (y usa `maxFontSizeMultiplier`).

## Safe areas y edge-to-edge
- Usa `react-native-safe-area-context` (`SafeAreaView` o `useSafeAreaInsets`). El `SafeAreaView` de `react-native` está deprecado y no sirve en Android.
- Android dibuja edge-to-edge en las versiones actuales de Expo: siempre aplica insets inferiores (barra de gestos) en footers y botones fijos.
- Con header nativo de Stack, no apliques inset superior (el header ya lo gestiona); aplica `edges={['bottom']}` o insets manuales.
- En `ScrollView`/listas prefiere `contentInsetAdjustmentBehavior="automatic"` (iOS) o `contentContainerStyle={{ paddingBottom: insets.bottom }}`.

## Teclado
- Formularios simples: `KeyboardAvoidingView` con `behavior={Platform.OS === 'ios' ? 'padding' : undefined}`.
- Formularios largos o chat: `react-native-keyboard-controller` (`KeyboardProvider` en el root layout, `KeyboardAwareScrollView`, `KeyboardToolbar`). Requiere dev build (no Expo Go).
- `keyboardShouldPersistTaps="handled"` en ScrollViews con inputs y botones.
- Encadena inputs: `returnKeyType="next"` + `ref.current?.focus()`; `submitBehavior`/`blurOnSubmit` según versión de RN.
- Tipos correctos: `keyboardType`, `autoComplete`, `textContentType` (iOS), `secureTextEntry`, `autoCapitalize="none"` en emails.

## Listas
- Nunca `ScrollView` + `.map()` para colecciones de tamaño desconocido.
- `FlatList` para listas moderadas; `@shopify/flash-list` si el proyecto la tiene o la lista es larga/compleja. FlashList v2 requiere New Architecture y **ya no usa `estimatedItemSize`**; en v1 sí es obligatorio. Verifica la versión.
```tsx
import { FlashList } from '@shopify/flash-list';
import { memo, useCallback } from 'react';

const OrderRow = memo(function OrderRow({ order, onPress }: { order: Order; onPress: (id: string) => void }) {
  return <Pressable onPress={() => onPress(order.id)}>{/* ... */}</Pressable>;
});

export function OrderList({ orders, onSelect, onEndReached, refreshing, onRefresh }: OrderListProps) {
  const renderItem = useCallback(({ item }: { item: Order }) => <OrderRow order={item} onPress={onSelect} />, [onSelect]);
  return (
    <FlashList
      data={orders}
      renderItem={renderItem}
      keyExtractor={(item) => item.id}
      onEndReached={onEndReached}
      onEndReachedThreshold={0.5}
      refreshing={refreshing}
      onRefresh={onRefresh}
      ListEmptyComponent={<EmptyState title="Sin pedidos" />}
    />
  );
}
```
- `keyExtractor` con id estable (nunca el índice si la lista cambia).
- Items memoizados; `renderItem` y callbacks estables con `useCallback`.
- FlashList recicla vistas: no pongas `key` en el árbol de `renderItem` y cuidado con `useState` local (se "hereda" entre items; en v2 existe `useRecyclingState`).
- Tipos de fila heterogéneos: `getItemType`.
- `FlatList`: `getItemLayout` si la altura es fija; ajusta `windowSize`/`initialNumToRender` solo midiendo.

## Imágenes: expo-image
```tsx
import { Image } from 'expo-image';

<Image
  source={{ uri: product.imageUrl }}
  placeholder={{ blurhash: product.blurhash }}
  contentFit="cover"
  transition={200}
  recyclingKey={product.id}      // en listas recicladas
  accessibilityLabel={product.name}
  style={{ width: 96, height: 96, borderRadius: 8 }}
/>
```
- Siempre dimensiones explícitas (o `aspectRatio`) para evitar saltos de layout.
- Pide al backend tamaños adecuados; no descargues 4000px para un thumbnail.
- Imágenes decorativas: `accessible={false}`; informativas: `accessibilityLabel`.

## Gestos y animaciones
- Animaciones con `react-native-reanimated` (v4 solo New Architecture; worklets en paquete `react-native-worklets`, el plugin de Babel ya viene en `babel-preset-expo`). Anima `transform` y `opacity`, no `width/height/top` si puedes evitarlo.
- Gestos con `react-native-gesture-handler`; requiere `GestureHandlerRootView` en el root layout. La API cambió en v3 (hooks como `usePanGesture`); en v2 se usa `Gesture.Pan()`. **Revisa la versión instalada.**
- Lee `references/animations-gestures.md` para ejemplos de ambas APIs, layout animations y reglas de hilo UI/JS.

## Accesibilidad (obligatorio)
- Todo elemento interactivo: `accessibilityRole` (o `role`), `accessibilityLabel` si no tiene texto visible, `accessibilityState` (disabled, selected, checked, busy, expanded).
- `accessibilityHint` solo si la acción no es obvia.
- Área táctil mínima 44×44 pt (iOS) / 48×48 dp (Android): usa `hitSlop` o `minHeight`.
- Agrupa contenido relacionado (`accessible` en el contenedor de una card) para que el lector lo lea de una vez.
- Anuncia cambios importantes: `AccessibilityInfo.announceForAccessibility`.
- Respeta reduce motion (`useReducedMotion` de Reanimated o `AccessibilityInfo.isReduceMotionEnabled`).
- Contraste mínimo WCAG AA (4.5:1 texto normal). Prueba con VoiceOver y TalkBack.

## Diferencias iOS/Android
- Usa `Platform.select` o archivos `.ios.tsx`/`.android.tsx` solo cuando la divergencia es grande.
- Sombras: iOS usa `shadow*`; Android `elevation`. En RN reciente existe `boxShadow` multiplataforma (New Architecture); verifica versión.
- Botón atrás hardware de Android: lo gestiona el navigator; para casos custom `BackHandler` dentro de `useFocusEffect`.
- Ripple: `android_ripple` en `Pressable`.
- Fuentes: `fontWeight` numérico se comporta distinto con fuentes custom en Android; carga variantes con `expo-font`.
- Lee `references/performance-platform.md` para la lista completa de diferencias y el checklist de rendimiento.

## Rendimiento (resumen)
- Mide antes de optimizar: React DevTools Profiler, perf monitor, builds release (Dev mode es mucho más lento).
- Evita re-renders: estado lo más local posible, selectores en stores, `memo` en items de lista, props estables.
- No hagas trabajo pesado en render; mueve cálculo a `useMemo` o fuera del componente.
- Si el proyecto usa React Compiler, no añadas `useMemo`/`useCallback` manuales innecesarios; sigue su configuración.
- Nada de `console.log` en loops calientes; elimina logs en producción.

## Antipatrones
- `ScrollView` con cientos de hijos o `FlatList` anidada en `ScrollView` con la misma orientación.
- Estilos/funciones inline en `renderItem`.
- `useEffect` para derivar estado que se puede calcular en render.
- `Dimensions.get` estático para layout responsivo (usa `useWindowDimensions`).
- Hardcodear `paddingTop: 44` para el notch.
- `TouchableOpacity`/`Image` de RN en código nuevo cuando el proyecto ya tiene `Pressable`/`expo-image`.
- Mezclar NativeWind y StyleSheet en el mismo componente sin razón.

## Checklist final
- [ ] Sigue el sistema de estilos y la estructura de carpetas del proyecto.
- [ ] Props tipadas, sin `any`, named export (salvo rutas).
- [ ] Safe areas e insets correctos en iOS y Android (edge-to-edge).
- [ ] Teclado no tapa inputs; `keyboardShouldPersistTaps` configurado.
- [ ] Listas virtualizadas con `keyExtractor` estable e items memoizados.
- [ ] Imágenes con dimensiones y `expo-image`.
- [ ] Roles, labels, estados y áreas táctiles de accesibilidad.
- [ ] Probado (o razonado) en iOS y Android, modo claro y oscuro, fuente grande.
- [ ] `npx tsc --noEmit` y lint sin errores.
