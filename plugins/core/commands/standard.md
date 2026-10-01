---
description: "Flujo completo de una feature aplicando los estándares completos de la suite (código, testing, stack y estándar de proyecto) y verificándolos al final con su checklist"
argument-hint: "[front|back|ia|mobile|devops] <descripción de la tarea o feature>"
---

Desarrolla con los estándares completos: $ARGUMENTS

Si `$ARGUMENTS` está vacío, pide la descripción de la tarea y detente.

## 1. Cargar contexto y fijar los estándares

1. Carga `core:project-context`, ejecuta el detector de stack y lee `CLAUDE.md`/`AGENTS.md`.
2. **Especialidad**: si la primera palabra de `$ARGUMENTS` es una especialidad (`front`, `back`, `ia`, `mobile`, `devops` o sus alias), aplica las reglas de `core:project-context` §3.1: estándares, agentes, reviewer y verificación se limitan a esa especialidad, y todo cambio fuera de ella se reporta como dependencia en vez de hacerse. Sin especialidad, sigue la autodetección de abajo.
3. Arma la **lista de estándares obligatorios** para esta tarea (con especialidad, solo las filas de abajo que correspondan a ella):
   - Siempre: `core:coding-standards`, `core:testing-strategy`, `core:code-review-checklist`, `core:documentation-standards`.
   - Next.js: `frontend:nextjs-project-standard` (completo, aunque el proyecto ya exista), `frontend:nextjs-app-router`, `frontend:react-components`, `frontend:typescript-patterns`, `frontend:frontend-testing`.
   - React sin Next: `frontend:react-components`, `frontend:typescript-patterns`, `frontend:frontend-testing`.
   - Expo / React Native: `mobile:expo-project-standard` (completo, aunque el proyecto ya exista), `mobile:react-native-components`, `mobile:expo-router-navigation`, `mobile:mobile-state-data`, `mobile:mobile-testing`.
   - Backend, IA y devops: todas las skills del mapa de `core:project-context` para los stacks que toca la tarea (p. ej. `backend:fastapi-endpoint` + `backend:database-patterns` + `backend:backend-testing`; `backend:langgraph-agents` + `backend:langsmith-observability`).
4. Muestra la lista al usuario en una línea por skill, indicando la especialidad si la hay.

**Precedencia**: `CLAUDE.md` del proyecto > estándar de proyecto (`*-project-standard`) > skills de stack > `core:coding-standards`. Si el código existente contradice el estándar, el código **nuevo** sigue el estándar; no migres código existente fuera del alcance: anota la desviación y pregunta.

## 2. Fases

Ejecuta las fases de `/feature` en el mismo orden y con la misma confirmación antes de implementar. A **cada agente** que lances pásale la lista de estándares obligatorios y la instrucción de cargarlos con `Skill` antes de trabajar.

1. **Plan** — `core:planner`. Cada paso del plan indica qué estándar aplica (estructura de carpetas, naming, estado, formularios, errores, tests).
2. **Diseño** (si el plan requiere ADR) — `core:architect`.
3. **Implementación** — tras la confirmación del usuario, el especialista de stack o `core:coder`, según `/implement`.
4. **Tests** — `core:tester`, con las reglas de testing del estándar (tipos de test, cobertura de estados de carga/error/vacío, sin red).
5. **Review** — `core:reviewer` + reviewer de stack en paralelo, **revisando contra la lista de estándares**. Hallazgos 🔴/🟠 o incumplimientos del estándar → vuelve a la fase 3 (máximo 2 iteraciones).
6. **Documentación** — `core:documenter`.

## 3. Verificación final del estándar

1. Ejecuta los scripts de calidad del proyecto que existan (`lint`, `typecheck`, `test`, `build`) y reporta el resultado real.
2. Recorre el **Final Checklist** de cada `*-project-standard` aplicado, ítem por ítem, sobre los archivos cambiados: ✅ cumple · ❌ no cumple (con archivo y motivo) · N/A.
3. Si queda algún ❌ que no se pudo corregir, dilo explícitamente; no declares la tarea terminada como "cumple el estándar".

Resumen final:

```markdown
## <nombre de la tarea>
- Especialidad: <front | back | ia | mobile | devops | autodetectada>
- Estándares aplicados: ...
- Plan / ADR: ...
- Archivos cambiados: ...
- Verificación: <comando> → resultado
- Checklist del estándar: X ✅ · Y ❌ · Z N/A (detalle de los ❌)
- Desviaciones del código existente (no migradas): ...
- Dependencias fuera de la especialidad (no hechas): ...
- Review: veredicto y hallazgos pendientes
- Siguiente paso: commit / PR (solo si el usuario lo pide, siguiendo core:git-workflow)
```
