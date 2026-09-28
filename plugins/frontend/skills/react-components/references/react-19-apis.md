# APIs de React 19.x con ejemplos

Lee este archivo cuando uses actions, `use`, `useOptimistic`, o APIs de 19.2/19.3. Confirma primero la versión de `react` en `package.json`.

| API | Desde | Import |
|---|---|---|
| `use(promise | context)` | 19.0 | `react` |
| `useActionState` | 19.0 | `react` (reemplaza `useFormState` de `react-dom`) |
| `useFormStatus` | 19.0 | `react-dom` |
| `useOptimistic` | 19.0 | `react` |
| `ref` como prop, cleanup en ref callbacks | 19.0 | — |
| `<Context value>` como provider | 19.0 | — |
| `<title>`, `<meta>`, `<link>` en cualquier componente | 19.0 | — |
| `useEffectEvent` | 19.2 | `react` |
| `<Activity mode="visible" \| "hidden">` | 19.2 | `react` |
| `<ViewTransition>`, `addTransitionType` | 19.3 (estable) | `react` |
| Fragment refs (`<Fragment ref>`) | 19.3 | `react` |
| `browser()` | 19.3 | `react-dom` |

## `use`

Lee una Promise (suspende hasta resolver) o un contexto. Puede llamarse dentro de condicionales.

```tsx
// page.tsx (Server Component): inicia la petición sin await y pásala
export default function Page() {
  const commentsPromise = getComments() // no await
  return (
    <Suspense fallback={<CommentsSkeleton />}>
      <Comments commentsPromise={commentsPromise} />
    </Suspense>
  )
}

// comments.tsx (Client Component)
'use client'
import { use } from 'react'

export function Comments({ commentsPromise }: { commentsPromise: Promise<Comment[]> }) {
  const comments = use(commentsPromise)
  return <ul>{comments.map((c) => <li key={c.id}>{c.text}</li>)}</ul>
}
```

- No crees la Promise dentro del Client Component en cada render (se recrea y suspende en bucle); créala en el servidor, en un loader o cachéala.
- Envuelve en un error boundary para manejar rechazos.

## `useActionState`

```tsx
const [state, formAction, isPending] = useActionState(action, initialState, permalink?)
```

- `action(prevState, formData)` puede ser una Server Action o una función async del cliente.
- `isPending` evita un `useFormStatus` extra si el botón está en el mismo componente.
- Tras el submit, React resetea los campos no controlados del `<form>`; para conservar valores, devuélvelos en `state` y úsalos como `defaultValue`.

## `useFormStatus`

Solo funciona en un componente **hijo** del `<form>` (lee el form padre más cercano):

```tsx
function SubmitButton() {
  const { pending } = useFormStatus()
  return <button type="submit" disabled={pending} aria-disabled={pending}>Enviar</button>
}
```

## `useOptimistic`

```tsx
'use client'
import { useOptimistic } from 'react'

type Todo = { id: string; text: string; pending?: boolean }

export function TodoList({ todos, addTodo }: { todos: Todo[]; addTodo: (text: string) => Promise<void> }) {
  const [optimisticTodos, addOptimistic] = useOptimistic(
    todos,
    (current, text: string) => [...current, { id: `temp-${current.length}`, text, pending: true }],
  )

  async function action(formData: FormData) {
    const text = String(formData.get('text') ?? '')
    addOptimistic(text)
    await addTodo(text) // al terminar, `todos` llega actualizado desde el servidor
  }

  return (
    <>
      <form action={action}>
        <input name="text" aria-label="Nueva tarea" />
        <button type="submit">Añadir</button>
      </form>
      <ul>
        {optimisticTodos.map((t) => (
          <li key={t.id} aria-busy={t.pending}>{t.text}</li>
        ))}
      </ul>
    </>
  )
}
```

- `addOptimistic` debe llamarse dentro de una action o de `startTransition`.
- Si la action falla, el estado optimista se descarta automáticamente al terminar la transición; muestra el error.

## `ref` como prop

```tsx
export function Input({ ref, ...props }: ComponentProps<'input'>) {
  return <input ref={ref} {...props} />
}
```

Los ref callbacks pueden devolver una función de cleanup. `forwardRef` sigue funcionando pero se desaconseja en código nuevo.

## `useEffectEvent` (19.2+)

Extrae lógica no reactiva de un efecto (leer el último valor sin re-ejecutar el efecto):

```tsx
function ChatRoom({ roomId, theme }: { roomId: string; theme: Theme }) {
  const onConnected = useEffectEvent(() => {
    showNotification('Conectado', theme) // lee el theme actual
  })

  useEffect(() => {
    const conn = createConnection(roomId)
    conn.on('connected', onConnected)
    conn.connect()
    return () => conn.disconnect()
  }, [roomId]) // theme no es dependencia
}
```

No lo pases a otros componentes ni lo llames durante el render.

## `<Activity>` (19.2+)

Oculta UI conservando su estado (y desmontando sus efectos) — tabs, paneles, pre-render de la siguiente pantalla:

```tsx
<Activity mode={tab === 'settings' ? 'visible' : 'hidden'}>
  <Settings />
</Activity>
```

## `<ViewTransition>` (19.3)

```tsx
import { ViewTransition, startTransition, addTransitionType } from 'react'

function next() {
  startTransition(() => {
    addTransitionType('next')
    setSlide((s) => s + 1)
  })
}

<ViewTransition enter={{ next: 'from-right' }} exit={{ next: 'to-left' }}>
  <Slide key={slide} />
</ViewTransition>
```

Solo anima actualizaciones dentro de transiciones (`startTransition`, `<Suspense>`, `useDeferredValue`, navegaciones del router). Respeta `prefers-reduced-motion` en el CSS.

## Fragment refs y `browser()` (19.3)

- `<Fragment ref={ref}>` expone un `FragmentInstance` con `focus()`, `addEventListener`, `observeUsing(observer)`, `getClientRects()`, etc. Útil para observar/enfocar grupos de hijos sin wrapper `<div>`.
- `use(browser())` (de `react-dom`) excluye un componente del SSR suspendiéndolo hasta el cliente; el `<Suspense>` más cercano muestra el fallback en el servidor. Alternativa moderna a `useEffect(() => setMounted(true))`.

## Metadata del documento

`<title>`, `<meta>` y `<link rel="stylesheet" precedence="default">` pueden renderizarse en cualquier componente y React los sube a `<head>`. En Next.js prefiere la Metadata API; úsalo en `global-error.tsx` o en SPAs sin framework.

## React Compiler

- Versión 1.0 estable. En Next 16: `reactCompiler: true` (top-level) + `babel-plugin-react-compiler`. En 16.3 hay un port en Rust experimental (`experimental.turbopackRustReactCompiler`). En Vite: plugin de Babel en `@vitejs/plugin-react`.
- Memoiza automáticamente; el código debe respetar las reglas de React (pureza en render, no mutar props/estado, hooks en top-level).
- Las reglas de lint del compilador vienen en `eslint-plugin-react-hooks` (versiones recientes); actívalas para detectar código que el compilador no puede optimizar.
- Opt-out puntual: directiva `'use no memo'` al inicio de un componente/hook.
