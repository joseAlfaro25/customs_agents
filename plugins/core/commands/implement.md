---
description: "Implementa una tarea o plan con el agente de código adecuado (general o especialista de stack)"
argument-hint: "<tarea o referencia al plan>"
---

Implementa: $ARGUMENTS

1. Si `$ARGUMENTS` está vacío y no hay un plan previo en esta conversación, pide la tarea y detente.
2. Carga la skill `core:project-context` y determina qué stacks toca la tarea.
3. Elige el agente:
   - Un solo stack y tarea especializada → el especialista del mapa de `core:project-context` (p. ej. `backend:fastapi-developer`, `frontend:nextjs-developer`, `backend:langgraph-developer`, `mobile:expo-developer`, `devops:devops-engineer`).
   - Varios stacks o tarea general → `core:coder`.
   - Si el plan tiene pasos independientes de stacks distintos, puedes lanzar varios agentes en paralelo, uno por paso, indicando a cada uno qué archivos le corresponden.
4. Pásale al agente el plan completo (o la tarea), los criterios de aceptación y los archivos relevantes.
5. Al terminar, muestra los cambios y el resultado de la verificación (typecheck, lint, tests).
6. Ofrece `/review` como siguiente paso. No hagas commit salvo que el usuario lo pida.
