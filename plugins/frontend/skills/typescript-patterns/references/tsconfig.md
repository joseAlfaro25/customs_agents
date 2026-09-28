# tsconfig: opciones, versiones y plantillas

Lee este archivo al crear, endurecer o migrar un `tsconfig.json`. Comprueba siempre la versión instalada (`npx tsc -v`) y la config efectiva (`npx tsc --showConfig`).

## Diferencias entre versiones mayores

| Tema | TS 5.x | TS 6.0 (puente) | TS 7.0 (nativo, jul 2026) |
|---|---|---|---|
| Compilador | JS (`tsc`) | JS; depreca opciones que 7 elimina | Port nativo en Go, ~10x más rápido; paquete `typescript`, binario `tsc` |
| `strict` por defecto | `false` | `true` (nuevo default) | `true` |
| `types` por defecto | todos los `@types/*` | `[]` (nuevo default) | `[]`: declara explícitamente `node`, `vitest/globals`, etc. |
| `baseUrl` | soportado | deprecado | **eliminado**: usa `paths` relativos al tsconfig |
| `moduleResolution: node`/`node10`/`classic` | soportado | deprecado | **eliminado**: usa `bundler` o `nodenext` |
| `target: es5`, `downlevelIteration` | soportado | deprecado | **eliminado** |
| `module: amd/umd/system/none` | soportado | deprecado | **eliminado** |
| `esModuleInterop: false` | soportado | deprecado | no se puede desactivar |
| `rootDir` | inferido | `./` (nuevo default) | `./` por defecto |
| `noUncheckedSideEffectImports` | `false` (5.6+) | — | `true` |

Los defaults de 6.0 se adelantaron para preparar la migración a 7; confirma en las release notes de la versión exacta instalada.

Compatibilidad: `@typescript/typescript6` aporta el binario `tsc6` para herramientas que aún dependan de la API JS del compilador. Algunas herramientas (plugins de editor, `ts-morph`, typescript-eslint) pueden ir por detrás: verifica su soporte antes de migrar a 7. Next.js 16.3 permite usar TS 7 en `next build`; Next 16 exige TS ≥ 5.1.

Si el proyecto usa TS 5.x, no introduzcas opciones de versiones posteriores; si migra a 7, elimina `baseUrl` y convierte `paths` a rutas relativas (`"@/*": ["./src/*"]`).

## Opciones recomendadas

| Opción | Efecto | Recomendación |
|---|---|---|
| `strict` | Activa `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`, etc. | Siempre `true` |
| `noUncheckedIndexedAccess` | Indexar arrays/records devuelve `T \| undefined` | Sí en código nuevo; en legacy, activar y corregir por módulos |
| `exactOptionalPropertyTypes` | `prop?: string` no acepta `undefined` explícito | Opcional; útil en librerías, ruidoso con algunas deps |
| `noImplicitOverride` | Exige `override` en clases | Sí |
| `noFallthroughCasesInSwitch` | Error en `case` sin `break` | Sí |
| `noImplicitReturns` | Todas las ramas devuelven | Sí |
| `verbatimModuleSyntax` | Imports de tipos deben ser `import type` | Sí con bundlers modernos |
| `isolatedModules` | Cada archivo transpilable por separado (SWC, esbuild) | Sí (Next y Vite lo requieren) |
| `erasableSyntaxOnly` (5.8+) | Prohíbe `enum`, `namespace`, parameter properties | Sí si usas type stripping de Node o quieres portabilidad |
| `skipLibCheck` | No chequea `.d.ts` de dependencias | Sí (velocidad) |
| `allowJs` / `checkJs` | Incluye JS | Solo durante migraciones |
| `incremental` | Cache de build `.tsbuildinfo` | Sí en proyectos grandes |

## Plantilla Next.js (App Router)

Next genera y ajusta partes de este archivo al ejecutar `next dev`/`next build` (por ejemplo `jsx`, `plugins` e `include` de tipos generados). No los elimines.

```jsonc
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- El valor de `jsx` lo gestiona Next; si lo cambia al arrancar, acepta su valor.
- `.next/types/**/*.ts` habilita los helpers globales `PageProps`, `LayoutProps`, `RouteContext` y rutas tipadas (`typedRoutes`).
- Con TS 7 y `types: []` por defecto, añade `"types": ["node"]` si usas `process`/`Buffer` fuera de archivos que ya los importan.

## Plantilla Vite + React

```jsonc
// tsconfig.app.json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "noEmit": true,
    "skipLibCheck": true,
    "types": ["vite/client"],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"]
}
```

## Tests

- Vitest con `globals: true`: añade `"types": ["vitest/globals"]` (y `@testing-library/jest-dom` si usas sus matchers sin import explícito) en el tsconfig que cubra los tests.
- Jest: `"types": ["jest", "@testing-library/jest-dom"]`.
- Separa si hace falta: `tsconfig.json` (app) y `tsconfig.test.json` con `extends`.

## Migración gradual a modo estricto

1. Activa `strict` y cuenta errores: `npx tsc --noEmit | grep -c "error TS"`.
2. Corrige por carpetas; donde no sea viable aún, `// @ts-expect-error TODO(strict): motivo`.
3. Añade un check en CI que impida aumentar el número de errores o de `@ts-expect-error`.
4. Después activa `noUncheckedIndexedAccess` y repite.
