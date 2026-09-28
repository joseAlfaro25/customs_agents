---
name: code-review-checklist
description: "Checklist general de code review para cualquier stack: corrección, seguridad, diseño, rendimiento, tests, legibilidad y formato de reporte con severidades. Cargar al revisar un diff, un PR o un cambio antes de commitear, junto con el reviewer del stack si aplica."
---

# code-review-checklist

El objetivo del review es encontrar **problemas reales** que el autor no vio, no reescribir el código al gusto del revisor.

## Cómo obtener el cambio

- Cambios locales: `git status`, `git diff` y `git diff --staged`.
- Rama: `git diff <base>...HEAD` (base = `main` salvo que el proyecto use otra) y `git log <base>..HEAD --oneline`.
- PR: `gh pr view <n>` y `gh pr diff <n>`.

Lee el diff **y** el contexto alrededor (archivo completo, llamadores de lo que cambió). Un bug suele estar en lo que el diff no muestra.

## Orden de revisión

1. **Intención**: ¿qué intenta hacer el cambio? (PR, commits, plan). Si no está claro, esa es la primera observación.
2. **Corrección** (lo más importante).
3. **Seguridad**.
4. **Datos y compatibilidad**.
5. **Tests**.
6. **Diseño y mantenibilidad**.
7. **Rendimiento**.
8. **Legibilidad y consistencia**.

## Checklist

### Corrección
- [ ] Hace lo que dice; cubre los criterios de aceptación.
- [ ] Casos límite: null/None/undefined, listas vacías, 0, strings vacíos, duplicados, concurrencia, zonas horarias.
- [ ] Manejo de errores: nada tragado; errores traducidos en la capa correcta; `await` no olvidados; promesas no manejadas.
- [ ] Lógica condicional: off-by-one, negaciones invertidas, `==` vs `===`, `is` vs `==` en Python.
- [ ] Estado: efectos de React con dependencias correctas; sin race conditions; cleanup.
- [ ] Llamadores del código modificado siguen funcionando.

### Seguridad
- [ ] Sin secretos, tokens ni credenciales en código, tests o logs.
- [ ] Entrada validada en el borde; SQL parametrizado; sin `eval`/ejecución dinámica de entrada.
- [ ] Autorización verificada en el servidor para cada recurso (no solo autenticación).
- [ ] Sin datos sensibles expuestos al cliente (`NEXT_PUBLIC_*`, `EXPO_PUBLIC_*`, respuestas de API con campos de más).
- [ ] XSS: sin HTML sin sanitizar. CSRF/CORS configurados si aplica.
- [ ] LLM: salida validada, tools con permisos mínimos, prompt injection considerada.
- [ ] Dependencias nuevas justificadas y confiables.

### Datos y compatibilidad
- [ ] Migraciones reversibles y compatibles con la versión anterior desplegada.
- [ ] Cambios de contrato de API compatibles o versionados (clientes mobile viejos).
- [ ] Variables de entorno nuevas documentadas en `.env.example` y en la infra.

### Tests
- [ ] Hay tests para el comportamiento nuevo y para el bug arreglado.
- [ ] Los tests fallarían si el código estuviera mal (asserts significativos).
- [ ] Sin red/LLM reales; sin sleeps; sin dependencia del orden.

### Diseño
- [ ] Respeta la arquitectura y límites de módulos (`core:architecture-principles`).
- [ ] Sin duplicación evitable ni abstracciones prematuras.
- [ ] Responsabilidades en la capa correcta (nada de lógica de negocio en controllers/componentes).

### Rendimiento
- [ ] Sin N+1, sin consultas sin índice en rutas calientes, listados paginados.
- [ ] Sin trabajo pesado en el render ni re-renders evitables obvios.
- [ ] Llamadas externas con timeout; sin llamadas secuenciales que podrían ser paralelas.
- [ ] Bundle: sin importar librerías enteras al cliente sin necesidad.

### Legibilidad
- [ ] Nombres claros; funciones cortas; sin código muerto ni comentado.
- [ ] Consistente con el resto del código y con `core:coding-standards`.

## Severidades

| Nivel | Significado | Bloquea merge |
|---|---|---|
| 🔴 **Crítico** | Bug, pérdida de datos, vulnerabilidad, rompe producción o contrato | Sí |
| 🟠 **Importante** | Comportamiento incorrecto en casos límite, falta de tests clave, deuda que costará caro | Sí, salvo acuerdo |
| 🟡 **Sugerencia** | Mejora de diseño, legibilidad o rendimiento no crítico | No |
| ⚪ **Nit** | Estilo/preferencia menor | No (y evita llenar el review de estos) |

## Formato del reporte

```markdown
## Review: <qué se revisó>

**Veredicto**: ✅ Aprobar | ⚠️ Aprobar con cambios | ❌ Cambios requeridos

**Resumen**: <2–3 líneas: qué hace el cambio y la impresión general>

### Hallazgos
1. 🔴 `ruta/archivo.ts:42` — <problema concreto>.
   **Escenario**: <entrada/estado → resultado incorrecto>.
   **Sugerencia**: <cómo arreglarlo, con snippet si ayuda>.
2. 🟠 ...

### Lo que está bien
- <1–3 puntos concretos, no relleno>

### Verificación ejecutada
- `pnpm test` → ✅ 120 passed / ❌ ...
```

## Reglas

- Cada hallazgo con **ubicación, escenario concreto y sugerencia**. "Esto podría fallar" sin escenario no es un hallazgo.
- Distingue hechos de dudas: si no estás seguro, dilo ("Posible: ...") y explica qué verificar.
- No reportes lo que el linter/formatter ya detecta automáticamente.
- Máximo ~15 hallazgos; si hay más, agrupa y prioriza.
- El reviewer no modifica código; propone.
