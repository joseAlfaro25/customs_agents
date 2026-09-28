---
description: "Diseña la arquitectura de una solución y registra la decisión como ADR usando el agente architect"
argument-hint: "<problema o decisión técnica a diseñar>"
---

Diseña la arquitectura para: $ARGUMENTS

1. Si `$ARGUMENTS` está vacío, pide al usuario el problema o la decisión a tomar y detente.
2. Delega en el agente `core:architect` con el problema, el contexto de la conversación y el plan previo si existe.
3. Presenta al usuario las opciones, la recomendación y el diseño propuesto.
4. Pregunta si se guarda el ADR en `docs/adr/` (si el architect no lo creó ya) y confirma la ruta.
5. Ofrece continuar con `/plan` para detallar la implementación.
