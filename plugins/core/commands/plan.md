---
description: "Crea un plan de implementación detallado para una tarea usando el agente planner"
argument-hint: "<descripción de la tarea o ticket>"
---

Planifica la siguiente tarea: $ARGUMENTS

1. Si `$ARGUMENTS` está vacío, pide al usuario que describa la tarea (qué quiere lograr y por qué) y detente.
2. Delega en el agente `core:planner` pasándole la tarea completa y cualquier contexto de esta conversación (archivos mencionados, tickets, restricciones).
3. Si el planner devuelve preguntas bloqueantes, muéstraselas al usuario tal cual y espera respuesta antes de continuar.
4. Presenta el plan final. Si indica que requiere ADR, ofrece ejecutar `/design`. Si no, ofrece ejecutar `/implement` con el plan.
5. No modifiques archivos en este comando.
