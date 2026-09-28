---
name: react-components
description: "Patrones para componentes React 19 con TypeScript: estructura por feature, props tipadas, composición, hooks personalizados, estado, formularios con actions, rendimiento, React Compiler y accesibilidad. Usar al crear, refactorizar o revisar componentes y hooks de UI."
---

# react-components

Convenciones para escribir componentes React mantenibles, accesibles y tipados. Referencia base: **React 19.x** (19.3 estable a septiembre 2026). **Verifica `react`, `react-dom` y `@types/react` en `package.json`**: `ref` como prop, `use`, `useActionState` y `<Context>` como provider requieren React 19; `useEffectEvent`/`<Activity>` requieren 19.2; `<ViewTransition>` y Fragment refs son estables desde 19.3.

## Cuándo aplicarla

- Crear un componente, hook o formulario nuevo.
- Refactorizar componentes grandes, props confusas o estado duplicado.
- Resolver problemas de rendimiento, re-renders o efectos mal usados.
- Revisar accesibilidad de UI interactiva.

## Paso 0: detectar convenciones del proyecto

Antes de escribir, busca 2–3 componentes existentes y replica:
- Ubicación (`src/components`, `src/features/*/components`, `app/**/_components`).
- Nombres de archivo (`Button.tsx` vs `button.tsx`), exports nombrados vs default, barrels (`index.ts`).
- Estilos (Tailwind, CSS Modules, styled-components, vanilla-extract) y librería UI (shadcn/ui, Radix, MUI).
- Utilidades (`cn()`/`clsx`, `cva`), librería de estado, formularios y data fetching.
- Ubicación y estilo de tests (`*.test.tsx` colocalizado o `__tests__/`).

Si el proyecto no tiene convención, usa la estructura por feature de abajo.

## Estructura por feature

```
src/
├─ components/            # UI genérica y reutilizable (sin lógica de negocio)
│  └─ ui/button/
│     ├─ button.tsx
│     ├─ button.test.tsx
│     └─ index.ts
├─ features/
│  └─ checkout/
│     ├─ components/      # UI específica del feature
│     ├─ hooks/           # use-cart.ts
│     ├─ api/             # llamadas, queries, schemas zod
│     ├─ types.ts
│     └─ index.ts         # API pública del feature
├─ hooks/                 # hooks genéricos (use-media-query.ts)
└─ lib/                   # utilidades puras
```

Reglas:
- Un feature no importa internals de otro: solo desde su `index.ts`.
- Un componente por archivo (subcomponentes privados pequeños pueden convivir).
- Evita barrels gigantes en `components/` que rompan tree-shaking o creen ciclos; un `index.ts` por componente/feature está bien.

## Props tipadas

```tsx
import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/utils'

type ButtonProps = ComponentProps<'button'> & {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  leftIcon?: ReactNode
}

export function Button({ variant = 'primary', size = 'md', leftIcon, className, children, ...props }: ButtonProps) {
  return (
    <button type="button" className={cn(styles({ variant, size }), className)} {...props}>
      {leftIcon}
      {children}
    </button>
  )
}
```

- Extiende props nativas con `ComponentProps<'button'>` (incluye `ref` en React 19; ya no hace falta `forwardRef`).
- Uniones literales para variantes, no `string`. Defaults en la desestructuración, no `defaultProps`.
- Props mutuamente excluyentes con discriminated unions (ver `frontend:typescript-patterns`).
- Callbacks como `onX` (`onSelect`, `onOpenChange`); booleanos como `isX`/`hasX` o adjetivos (`disabled`, `open`).
- Tipa `children` como `ReactNode`. No uses `React.FC` (no aporta y oculta el tipo de retorno).

## Composición antes que configuración

Prefiere `children` y slots a decenas de props booleanas.

```tsx
// Compound components con contexto (React 19: <Context value> sin .Provider)
const TabsContext = createContext<TabsState | null>(null)

function useTabs() {
  const ctx = use(TabsContext)
  if (!ctx) throw new Error('useTabs debe usarse dentro de <Tabs>')
  return ctx
}

export function Tabs({ defaultValue, children }: { defaultValue: string; children: ReactNode }) {
  const [value, setValue] = useState(defaultValue)
  return <TabsContext value={{ value, setValue }}>{children}</TabsContext>
}
Tabs.List = TabsList
Tabs.Trigger = TabsTrigger
Tabs.Panel = TabsPanel
```

- En Next.js, si el compound component es `'use client'` y se usa desde un Server Component, exporta cada parte por separado (`TabsList`, `TabsTrigger`): no se puede acceder a `Tabs.List` a través de la frontera cliente.
- Controlado/no controlado: acepta `value` + `onValueChange` y `defaultValue`; no sincronices props a estado con `useEffect`.
- Para UI compleja accesible (dialog, menu, combobox, tabs) reutiliza primitives (Radix, React Aria, Base UI) en lugar de reinventar.

## Hooks personalizados

```ts
// hooks/use-debounced-value.ts
import { useEffect, useState } from 'react'

export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(id)
  }, [value, delayMs])
  return debounced
}
```

- Nombre `useX`, un propósito, retorno tipado (objeto si >2 valores; tupla `as const` si imita `useState`).
- Extrae lógica cuando se repite o cuando el componente mezcla varias responsabilidades.
- Respeta las reglas de hooks; nunca llames hooks condicionalmente (excepto `use`, que sí puede ir en condicionales).

## Estado

| Necesidad | Herramienta |
|---|---|
| UI local (abierto, input) | `useState` / `useReducer` |
| Derivable de props/estado | Calcúlalo en render (sin estado ni efecto) |
| URL compartible (filtros, página, tab) | Search params (`useSearchParams` / `nuqs` si existe) |
| Datos del servidor | Server Components, o TanStack Query/SWR en cliente |
| Compartido poco cambiante (tema, sesión) | Context |
| Global cliente frecuente | Zustand/Jotai/Redux Toolkit **si el proyecto ya lo usa** |

- No dupliques datos del servidor en estado global.
- Coloca el estado lo más cerca posible de donde se usa; súbelo solo cuando dos hermanos lo necesiten.
- `useEffect` es para sincronizar con sistemas externos (suscripciones, DOM, timers). No lo uses para derivar estado, reaccionar a eventos o hacer fetch que puede ir en el servidor.
- Para leer el último valor dentro de un efecto sin re-suscribir, usa `useEffectEvent` (19.2+).

## Formularios

Con React 19 (y Next.js Server Actions):

```tsx
'use client'
import { useActionState } from 'react'
import { useFormStatus } from 'react-dom'
import { createPost, type CreatePostState } from './actions'

function SubmitButton() {
  const { pending } = useFormStatus()
  return <button type="submit" disabled={pending}>{pending ? 'Guardando…' : 'Guardar'}</button>
}

export function PostForm() {
  const [state, formAction] = useActionState<CreatePostState, FormData>(createPost, {})
  return (
    <form action={formAction} noValidate>
      <label htmlFor="title">Título</label>
      <input id="title" name="title" required aria-invalid={!!state.errors?.title} aria-describedby="title-error" />
      {state.errors?.title && <p id="title-error" role="alert">{state.errors.title[0]}</p>}
      <SubmitButton />
    </form>
  )
}
```

- Formularios simples: actions + `useActionState`. Formularios complejos (campos dinámicos, validación en vivo): React Hook Form + `zodResolver` si el proyecto lo usa.
- Valida con el mismo schema zod en cliente y servidor; el servidor siempre revalida.
- `useOptimistic` para feedback inmediato (likes, listas). Detalle y ejemplos: [references/react-19-apis.md](references/react-19-apis.md).

## Rendimiento

1. **Mide primero** (React DevTools Profiler, Web Vitals). No optimices a ciegas.
2. **React Compiler** (1.0 estable): si el proyecto lo tiene activo (`reactCompiler: true` en Next o `babel-plugin-react-compiler`), **no añadas** `useMemo`/`useCallback`/`memo` manuales; escribe código idiomático que cumpla las reglas de React.
3. Sin compilador: `memo`/`useMemo`/`useCallback` solo cuando el profiler muestre un coste real o para estabilizar dependencias de un hijo memoizado.
4. Antes de memoizar: mueve el estado hacia abajo, pasa contenido como `children`, divide componentes.
5. Listas largas: virtualiza (`@tanstack/react-virtual`). Keys estables (id), nunca el índice si la lista se reordena.
6. Código pesado: `lazy()` + `<Suspense>` (en Next: `next/dynamic`). `useTransition`/`useDeferredValue` para mantener la UI responsiva.

## Accesibilidad (obligatoria)

- HTML semántico primero: `<button>` para acciones, `<a href>` para navegación, `<label>` asociado a cada input.
- Todo interactivo es operable con teclado y tiene foco visible; nada de `div onClick`.
- Imágenes con `alt` (vacío si decorativas). Iconos-botón con `aria-label`.
- Errores de formulario vinculados con `aria-describedby` y `aria-invalid`; mensajes dinámicos con `role="alert"` o `aria-live`.
- Diálogos: foco atrapado, `Escape` cierra, foco vuelve al disparador (usa primitives).
- Contraste AA, `prefers-reduced-motion` para animaciones, sin depender solo del color.
- Usa `eslint-plugin-jsx-a11y` si está configurado y testea con queries por rol (`frontend:frontend-testing`).

## Antipatrones

- `useEffect` para derivar estado o para "sincronizar" props → estado.
- Componentes de 300+ líneas con fetch, estado, lógica y UI mezclados.
- Prop drilling de más de 2–3 niveles sin considerar composición o contexto.
- `any` en props, `as` para silenciar errores, `React.FC`.
- `forwardRef` nuevo en proyectos React 19 (usa `ref` como prop).
- Memoización manual con React Compiler activo, o memo en todo "por si acaso".
- Crear componentes dentro de otros componentes (remonta en cada render).
- Keys con `Math.random()` o índice en listas mutables.

## Checklist final

- [ ] Ubicación, nombre y estilo siguen las convenciones existentes.
- [ ] Props tipadas, extienden nativas cuando envuelven un elemento, sin `any`.
- [ ] Sin estado derivado ni efectos innecesarios.
- [ ] Accesible con teclado y lector de pantalla; roles y labels correctos.
- [ ] Test del comportamiento principal (render, interacción, estados de error/carga).
- [ ] Exportado desde el `index.ts` correspondiente si el proyecto usa barrels.
- [ ] `tsc --noEmit`, lint y tests pasan.

## Skills relacionadas

- `frontend:nextjs-app-router` si el componente vive en `app/` o usa Server Actions.
- `frontend:typescript-patterns` para tipos avanzados de props y genéricos.
- `frontend:frontend-testing` para escribir sus tests.
- `core:coding-standards` para principios generales.
