---
description: "Crea o actualiza documentación (README, ADR, API, runbook, changelog) con el agente documenter"
argument-hint: "[qué documentar; vacío = cambios actuales]"
---

Documenta: $ARGUMENTS

1. Si `$ARGUMENTS` está vacío, documenta los cambios actuales de la rama (`git diff main...HEAD` y cambios locales): README, `.env.example`, docs de API y CHANGELOG según corresponda. Si no hay cambios, pregunta qué documentar.
2. Delega en el agente `core:documenter` con el objetivo, el diff o módulo y el contexto de la conversación.
3. Muestra los archivos de documentación creados o actualizados y lo que no se pudo verificar.
