---
description: "Flujo completo de una feature: planificar, diseñar si hace falta, implementar, testear, revisar y documentar"
argument-hint: "<descripción de la feature>"
---

Desarrolla la feature: $ARGUMENTS

Si `$ARGUMENTS` está vacío, pide la descripción de la feature y detente.

Ejecuta las fases en orden. Entre fases, muestra un resumen corto de lo hecho y **pide confirmación al usuario antes de pasar a la implementación** (fase 3). El resto continúa automáticamente salvo que haya bloqueos.

1. **Plan** — `core:planner` produce el plan. Si hay preguntas bloqueantes, pregúntalas y espera.
2. **Diseño** (solo si el plan indica que requiere ADR) — `core:architect` propone el diseño y el ADR.
3. **Implementación** — tras la confirmación del usuario, sigue las reglas de `/implement`: especialista de stack o `core:coder`; en paralelo si hay pasos independientes de stacks distintos.
4. **Tests** — `core:tester` cubre los criterios de aceptación del plan y ejecuta la suite afectada.
5. **Review** — igual que `/review`: `core:reviewer` + reviewers de stack en paralelo. Si hay hallazgos 🔴 o 🟠, vuelve a la fase 3 para corregirlos (máximo 2 iteraciones; después reporta lo pendiente).
6. **Documentación** — `core:documenter` actualiza README, `.env.example`, docs de API y CHANGELOG según el cambio.

Resumen final:

```markdown
## Feature: <nombre>
- Plan: <resumen / pasos>
- ADR: <ruta o "no aplica">
- Archivos cambiados: ...
- Tests: <comando> → resultado
- Review: veredicto y hallazgos pendientes
- Docs: ...
- Siguiente paso: commit / PR (solo si el usuario lo pide, siguiendo core:git-workflow)
```
