---
description: "Crea un componente React con TypeScript, su test y su export siguiendo la estructura del proyecto. Úsalo para generar un componente nuevo de UI o de un feature."
argument-hint: "<NombreComponente> [ruta-o-feature] [descripción breve]"
---

# /new-component

Argumentos recibidos: `$ARGUMENTS`

## 1. Validar argumentos

- El primer token de `$ARGUMENTS` es el nombre del componente. Si `$ARGUMENTS` está vacío, **detente y pregunta** el nombre del componente, dónde debe vivir (UI genérica o feature) y qué debe hacer.
- Normaliza el nombre a PascalCase para el componente (`user-card` → `UserCard`). Rechaza nombres que no sean identificadores válidos o que colisionen con elementos HTML/nombres reservados (`Button` está bien si el proyecto no lo tiene ya; `Object` no).
- El segundo token opcional es una ruta (`src/features/checkout/components`) o un feature (`checkout`). El resto es la descripción del comportamiento.
- Si ya existe un componente con ese nombre en el destino, **no lo sobrescribas**: informa y pregunta si se quiere otro nombre o modificar el existente.

## 2. Cargar contexto y skills

1. Carga `core:project-context` y lee `CLAUDE.md` y `package.json` (versiones de `react`, `typescript`, runner de tests, librería de estilos y UI).
2. Carga `frontend:react-components` y `frontend:frontend-testing`. Si el destino está dentro de `app/` (Next.js), carga también `frontend:nextjs-app-router`.

## 3. Detectar convenciones existentes

Busca 2–3 componentes similares (`Glob` sobre `src/components/**`, `src/features/**/components/**`, `app/**/_components/**`) y determina:

- **Ubicación**: carpeta por componente (`button/button.tsx` + `index.ts`) o archivo plano (`Button.tsx`).
- **Nombre de archivo**: kebab-case (`user-card.tsx`) o PascalCase (`UserCard.tsx`).
- **Exports**: nombrados o default; si existen barrels (`index.ts`) en la carpeta padre.
- **Estilos**: Tailwind + `cn()`, CSS Modules (`*.module.css`), styled-components, etc.
- **Tests**: colocalizados (`*.test.tsx`) o en `__tests__/`; runner (Vitest/Jest) e imports usados; si hay `renderWithProviders`.
- **Stories**: si el proyecto tiene Storybook (`*.stories.tsx`) junto a los componentes, créala también.

Si no hay convención previa, usa: `src/components/<kebab-name>/<kebab-name>.tsx`, `<kebab-name>.test.tsx`, `index.ts`, exports nombrados.

## 4. Crear el componente

- Función con export nombrado (o default si el proyecto lo usa), props tipadas con `type <Nombre>Props`.
- Si envuelve un elemento nativo, extiende `ComponentProps<'elemento'>`, propaga `...props` y `className`; en React 19 `ref` llega como prop (sin `forwardRef`). En React 18, usa `forwardRef` solo si necesita ref.
- Variantes con uniones literales; defaults en la desestructuración.
- Sin `'use client'` salvo que use estado, efectos, eventos o APIs del navegador (solo relevante en Next.js/RSC).
- HTML semántico y accesible: roles, labels, foco, `alt`, estados `disabled`/`aria-*` cuando apliquen.
- Sin `any`; sin memoización manual si el React Compiler está activo.

## 5. Crear el test

- Mismo runner, ubicación e imports que los tests existentes.
- Mínimo: renderiza con props requeridas y verifica por **rol/label/texto**; una interacción principal con `userEvent.setup()` si es interactivo; un estado alternativo (disabled, error, vacío) si existe.
- Sin snapshots grandes ni `getByTestId` si hay alternativa accesible.

## 6. Exportar

- Crea `index.ts` en la carpeta del componente si esa es la convención (`export { UserCard } from './user-card'` y `export type { UserCardProps } from './user-card'`).
- Si existe un barrel en la carpeta padre (`src/components/index.ts`, `features/<x>/index.ts`), añade el export manteniendo el orden existente.

## 7. Verificar

Ejecuta con el gestor de paquetes del proyecto (según lockfile) y corrige hasta que pasen:

1. Typecheck: script `typecheck` o `npx tsc --noEmit`.
2. Lint sobre los archivos nuevos: `npx eslint <archivos>` (o el script `lint`).
3. Test del componente: `npx vitest run <ruta-del-test>` o `npx jest <ruta-del-test>`.

## 8. Entregar

Responde con: archivos creados/modificados, la API de props, un ejemplo de uso de 3–6 líneas y el resultado de cada verificación. Si algo no pudo verificarse, indícalo.
