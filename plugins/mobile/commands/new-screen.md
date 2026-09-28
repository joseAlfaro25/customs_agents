---
description: "Crea una pantalla nueva en Expo Router (ruta, layout si hace falta, tipos, hook de datos, estados de carga/error/vacío y test) siguiendo la estructura del proyecto. Ej: /new-screen orders/[orderId]"
argument-hint: "<ruta-en-app> [descripción opcional]"
---

# /new-screen

Argumentos recibidos: `$ARGUMENTS`

## 1. Validar el argumento
- El primer token de `$ARGUMENTS` es la **ruta** relativa a la carpeta de rutas, en formato de Expo Router (p. ej. `settings`, `orders/[orderId]`, `(app)/(tabs)/profile`, `onboarding/step-2`). El resto, si existe, es la **descripción** de lo que debe mostrar la pantalla.
- Si `$ARGUMENTS` está vacío, **detente y pide** la ruta (y opcionalmente qué datos muestra y si es modal/tab) antes de continuar.
- Normaliza: sin extensión, sin `/` inicial, segmentos en `kebab-case`, params dinámicos en `camelCase` entre corchetes (`[orderId]`). Si el nombre no es válido (espacios, mayúsculas en segmentos estáticos, caracteres raros), propone la versión corregida y confirma.
- Si ya existe un archivo para esa ruta (`<ruta>.tsx` o `<ruta>/index.tsx`), no lo sobrescribas: informa y pregunta qué hacer.

## 2. Contexto del proyecto
1. Carga `core:project-context`.
2. Carga `mobile:expo-router-navigation`, `mobile:react-native-components` y `mobile:mobile-testing`. Si la pantalla consume datos, carga también `mobile:mobile-state-data`.
3. Lee `CLAUDE.md`, `package.json` (versiones de `expo`, `expo-router`, `@testing-library/react-native`, librerías de estado/estilos), `app.json`/`app.config.ts` (`typedRoutes`, `scheme`) y `tsconfig.json` (alias `@/`).
4. Localiza la carpeta de rutas (`src/app/` o `app/`) y lee los `_layout.tsx` de la jerarquía donde irá la pantalla.
5. Busca una pantalla similar ya existente y úsala como plantilla de estilo (estructura, imports, componentes UI, manejo de estados, ubicación de tests).

## 3. Decidir ubicación y layout
- Determina el grupo correcto: ¿pública o protegida por auth (dentro del grupo con `Stack.Protected`)? ¿Dentro de una tab? ¿Es un modal?
- Crea `_layout.tsx` **solo si hace falta**: carpeta nueva con varias pantallas que necesitan su propio Stack, una tab con navegación interna, o un modal de varios pasos. Si el layout padre ya cubre el caso, no crees uno.
- Si es modal o necesita opciones (título, `presentation`, `headerShown`), añade/ajusta el `Stack.Screen` en el layout padre.
- Si la ruta debe aparecer como tab, añade el `Tabs.Screen` con icono y título en el layout de tabs.

## 4. Generar archivos
Adapta nombres y rutas a la convención del proyecto. Estructura típica para `orders/[orderId]` en la feature `orders`:

1. **Ruta** (`<carpeta-rutas>/.../orders/[orderId].tsx`): delgada, `export default`.
   - Lee params con `useLocalSearchParams<{ orderId: string }>()` y valídalos.
   - Título dinámico con `<Stack.Screen options={{ title }} />` si aplica.
   - Delega en el componente de pantalla de la feature.
2. **Componente de pantalla** (`features/<feature>/components/<Name>Screen.tsx` o donde el proyecto los ponga): props tipadas, maneja **cuatro estados**:
   - Carga: indicador accesible (`accessibilityLabel="Cargando"`) o skeleton.
   - Error: mensaje comprensible + botón "Reintentar" (`accessibilityRole="button"`) que llama `refetch`.
   - Vacío: estado vacío con acción si aplica.
   - Éxito: contenido; listas con `FlatList`/`FlashList`.
   - Safe area/insets correctos, soporte de teclado si hay inputs, estilos con el sistema del proyecto.
3. **Tipos y datos** (si consume API): schema/tipo en `features/<feature>/api/*.schemas.ts`, función en `*.api.ts` y hook con TanStack Query en `*.queries.ts` usando la key factory de la feature (créala si no existe). Reutiliza el cliente HTTP existente.
4. **Test** (`__tests__/<Name>Screen.test.tsx` o `*.test.tsx`, según convención):
   - Renderiza con `QueryClientProvider` nuevo (`retry: false`) y mocks de la capa de API.
   - Casos: carga → éxito, error con reintento, vacío.
   - Si hay navegación desde/hacia la pantalla, un test con `renderRouter` de `expo-router/testing-library`.
   - Usa `await` en `render`/`userEvent` según la versión de RNTL.
5. **Navegación hacia la pantalla**: si la descripción lo indica, añade el `Link`/`router.push` tipado desde la pantalla de origen.

Si no se describieron datos, genera la pantalla con contenido placeholder mínimo y sin capa de API (sin inventar endpoints), y déjalo indicado en el resumen.

## 5. Verificar
Ejecuta y corrige hasta que pasen (solo lo que exista en el proyecto):
1. Si usa typed routes y `tsc` no reconoce la ruta nueva, indícalo: los tipos se regeneran al iniciar `npx expo start`.
2. `npx tsc --noEmit`
3. Lint: `npm run lint` (o `npx expo lint`).
4. Tests del archivo nuevo: `npx jest <ruta-del-test>` (o el script `test` con `--watchAll=false`).

## 6. Resumen final
Entrega:
- Ruta resultante (URL, p. ej. `/orders/123`) y deep link (`<scheme>://orders/123`).
- Archivos creados/modificados con su propósito.
- Resultado de tsc, lint y tests.
- Decisiones tomadas (grupo, layout, modal/tab) y pendientes (endpoints por confirmar, textos, diseño).
