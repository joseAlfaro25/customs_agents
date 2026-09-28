---
description: "Revisa los cambios actuales, una rama o un PR con el agente reviewer y los reviewers de stack"
argument-hint: "[número de PR | rama | vacío = cambios locales]"
---

Revisa: $ARGUMENTS

1. Determina el alcance:
   - Vacío → cambios locales (`git diff`, `git diff --staged`); si no hay, la rama actual contra `main`.
   - Número → PR (`gh pr diff <n>`, `gh pr view <n>`).
   - Nombre de rama → `git diff main...<rama>`.
2. Identifica los stacks tocados por el diff (con `core:project-context`).
3. Lanza en paralelo:
   - `core:reviewer` con el alcance completo.
   - El reviewer especialista de cada stack con cambios significativos: `frontend:frontend-reviewer`, `backend:backend-reviewer`, `mobile:mobile-reviewer`, y `devops:security-auditor` si hay cambios en Dockerfiles, workflows, Kubernetes o Terraform.
4. Consolida los reportes: elimina duplicados, ordena por severidad (🔴 → ⚪) y da un único veredicto.
5. No modifiques código. Ofrece aplicar las correcciones con `/implement` si el usuario lo desea.
