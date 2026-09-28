---
name: git-workflow
description: "Flujo de git del equipo: ramas, Conventional Commits, tamaño de commits, descripción de PRs y reglas de seguridad (sin force push a main, sin secretos). Cargar al crear ramas, escribir commits o preparar un pull request."
---

# git-workflow

Si el repo ya tiene convenciones (ver `git log`, `CONTRIBUTING.md`, CLAUDE.md, commitlint), **síguelas**. Esto es el default.

## Reglas de seguridad

- **No commitees ni hagas push si el usuario no lo pidió.**
- Nunca trabajes directo en `main`/`master`: crea una rama.
- Nunca `git push --force` a ramas compartidas; en tu propia rama usa `--force-with-lease`.
- Nunca commitees `.env`, llaves, credenciales ni archivos generados (`dist/`, `.next/`, `node_modules/`, `__pycache__/`). Revisa `git diff --staged` antes de commitear.
- No uses `--no-verify` para saltar hooks; arregla lo que el hook reporta.
- No reescribas historia ya publicada.

## Ramas

Formato: `<tipo>/<ticket-opcional>-<descripcion-corta>`

```
feat/PROJ-123-export-orders-csv
fix/login-redirect-loop
chore/upgrade-next-15
```

Tipos: los mismos de Conventional Commits.

## Conventional Commits

```
<tipo>(<scope opcional>): <resumen en imperativo, ≤ 72 caracteres>

<cuerpo opcional: qué y por qué, no cómo>

<footer opcional: BREAKING CHANGE: ..., Refs: PROJ-123>
```

| Tipo | Uso |
|---|---|
| `feat` | Funcionalidad nueva para el usuario |
| `fix` | Corrección de bug |
| `refactor` | Cambio interno sin cambiar comportamiento |
| `perf` | Mejora de rendimiento |
| `test` | Solo tests |
| `docs` | Solo documentación |
| `build` | Dependencias, build, empaquetado |
| `ci` | Pipelines |
| `chore` | Mantenimiento que no encaja arriba |
| `style` | Formato sin cambio de lógica |

Scope = módulo o app (`api`, `web`, `mobile`, `orders`, `infra`).

Ejemplos:

```
feat(api): add CSV export endpoint for orders
fix(web): prevent redirect loop when session expires
refactor(orders): extract pricing rules into domain service
feat(api)!: rename /v1/users to /v1/accounts

BREAKING CHANGE: clients must use /v1/accounts.
```

## Tamaño de commits y PRs

- Un commit = un cambio lógico que compila y pasa tests.
- PR ideal: < 400 líneas cambiadas, un solo propósito. Separa refactor y feature en PRs distintos.
- Commits de la misma tarea pueden unirse con squash al mergear si es la política del repo.

## Pull requests

Plantilla de descripción: [references/pr-template.md](references/pr-template.md).

Antes de abrir el PR:

1. `git fetch` y rebase/merge con la rama base según la política del repo.
2. Typecheck, lint y tests en verde localmente.
3. Autorevisión del diff con `core:code-review-checklist`.
4. Docs y `.env.example` actualizados.

Con GitHub CLI: `gh pr create --title "<conventional title>" --body-file <archivo>` (solo si el usuario lo pidió).

## Recuperación segura

| Situación | Comando |
|---|---|
| Deshacer último commit local, conservar cambios | `git reset --soft HEAD~1` |
| Sacar un archivo del stage | `git restore --staged <archivo>` |
| Revertir un commit ya publicado | `git revert <sha>` |
| Encontrar trabajo "perdido" | `git reflog` |

Antes de cualquier comando destructivo (`reset --hard`, `clean -fd`, `checkout -- .`) confirma con el usuario: se pierden cambios sin commitear.
