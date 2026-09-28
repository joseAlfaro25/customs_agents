---
description: "Escribe o mejora tests para un archivo, módulo o los cambios actuales usando el agente tester"
argument-hint: "[ruta o descripción; vacío = cambios actuales]"
---

Escribe tests para: $ARGUMENTS

1. Si `$ARGUMENTS` está vacío, el objetivo son los cambios actuales: `git diff` y `git diff --staged` (y los commits de la rama respecto a la base). Si no hay cambios, pide al usuario qué testear y detente.
2. Delega en el agente `core:tester` indicando el objetivo, los criterios de aceptación conocidos y el stack.
3. Muestra los tests creados, el comando ejecutado y su resultado.
4. Si el tester detectó bugs en el código de producción, preséntalos destacados y pregunta si se corrigen con `/implement`.
