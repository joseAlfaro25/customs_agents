---
description: "Implementa una tarea o plan con el agente de código adecuado (general o especialista de stack)"
argument-hint: "[front|back|ia|mobile|devops] <tarea o referencia al plan>"
---

Implementa: $ARGUMENTS

1. Si `$ARGUMENTS` está vacío y no hay un plan previo en esta conversación, pide la tarea y detente.
2. Carga la skill `core:project-context` y determina qué stacks toca la tarea. Si la primera palabra de `$ARGUMENTS` es una especialidad (`front`, `back`, `ia`, `mobile`, `devops` o sus alias), aplica §3.1: ese es el único frente, solo se toman los agentes de su fila y los pasos del plan que correspondan a otra especialidad se reportan sin ejecutarse.
3. Elige el agente:
   - Un solo stack y tarea especializada → el especialista del mapa de `core:project-context` (p. ej. `backend:fastapi-developer`, `frontend:nextjs-developer`, `backend:langgraph-developer`, `mobile:expo-developer`, `devops:devops-engineer`). Con especialidad, elige entre los agentes de su fila; si ninguno encaja, `core:coder` limitado a esa especialidad.
   - Varios stacks o tarea general → `core:coder`.
   - Si el plan tiene pasos independientes de stacks distintos, puedes lanzar varios agentes en paralelo, uno por paso, indicando a cada uno qué archivos le corresponden.
4. Pásale al agente el plan completo (o la tarea), los criterios de aceptación y los archivos relevantes.
5. Al terminar, muestra los cambios y el resultado de la verificación (typecheck, lint, tests).
6. Ofrece `/review` como siguiente paso. No hagas commit salvo que el usuario lo pida.
