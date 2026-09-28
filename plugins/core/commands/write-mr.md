---
description: "Escribe la descripción de un merge request / pull request con qué se hizo, por qué y cómo, a partir del diff, los commits y la conversación; opcionalmente lo crea en GitLab o GitHub"
argument-hint: "[rama base] [--create] [--draft] (vacío = rama actual contra la rama por defecto)"
---

Escribe el MR para: $ARGUMENTS

## 1. Alcance

1. Carga `core:project-context` y `core:git-workflow` (plantilla en su `references/pr-template.md`).
2. Rama base: la indicada en `$ARGUMENTS`; si no hay, la rama por defecto (`git symbolic-ref --short refs/remotes/origin/HEAD`, o `main`/`master`/`develop` si falla). Si la rama actual **es** la base, detente y avisa: no hay nada que describir.
3. Reúne el material real, sin inventar:
   - `git log --no-merges --format='%h %s%n%b' <base>..HEAD`
   - `git diff --stat <base>...HEAD` y `git diff <base>...HEAD` (en diffs grandes, lee por archivo lo relevante).
   - Ticket: de `$ARGUMENTS`, del nombre de la rama (p. ej. `feat/PROJ-123-...`) o de los commits.
   - De esta conversación, si existen: el plan, el ADR, el resumen de `/feature` o `/standard`, los comandos de verificación que se ejecutaron y sus resultados.
4. Si hay cambios sin commitear (`git status --short`), avisa de que **no** estarán en el MR y pregunta si seguir.

## 2. Plataforma y plantilla

- GitLab si el remoto contiene `gitlab` o existe `.gitlab-ci.yml`; GitHub si contiene `github`. Si no se puede saber, pregunta solo cuando vayas a crearlo.
- Si el repo tiene plantilla propia, **úsala en lugar de la de la suite**: `.gitlab/merge_request_templates/*.md` (la `Default.md` o la única) o `.github/pull_request_template.md` / `.github/PULL_REQUEST_TEMPLATE/*.md`.

## 3. Escribir la descripción

Idioma: el de los MRs/commits recientes del repo; si no hay señal, español.

**Título**: Conventional Commit (`feat(scope): ...`), ≤ 72 caracteres, con el ticket si el repo lo acostumbra.

**Cuerpo** (plantilla de `core:git-workflow`, adaptada):

- **Qué**: 1–3 líneas con el resultado visible del cambio, no la lista de archivos.
- **Por qué**: problema o necesidad y link al ticket.
- **Cómo**: agrupado por área o capa (UI, API, datos, agente, infra), no por commit. Por cada grupo: qué se cambió, los archivos clave y la decisión relevante para el reviewer. Incluye alternativas descartadas y estándares aplicados si los hubo.
- **Cómo probarlo**: pasos reproducibles, con comandos, rutas, datos de prueba y resultado esperado.
- **Verificación**: solo comandos que **realmente** se ejecutaron (en esta conversación o ahora) con su resultado. Si no se ejecutaron, córrelos si son rápidos (`lint`, `typecheck`, `test`) o escribe "no ejecutado". Nunca marques un check como hecho sin evidencia.
- **Riesgos y despliegue**: migraciones, variables de entorno nuevas (`.env.example`), feature flags, breaking changes, orden de despliegue, cómo revertir. Omite la sección si no aplica.
- **Checklist**: la de la plantilla, marcada según la evidencia.
- **Capturas**: si hay cambios de UI, deja el hueco indicado ("Agregar captura de /orders").

Reglas: sé concreto y breve (el reviewer lee esto antes del diff); nada de secretos, tokens ni datos personales; no copies el diff.

Si el diff supera ~400 líneas o mezcla propósitos (refactor + feature), dilo y sugiere cómo dividirlo, sin bloquear.

## 4. Entregar

1. Guarda la descripción en `$(git rev-parse --git-dir)/MR_DESCRIPTION.md` (dentro de `.git`, no se versiona) y muéstrala completa con el título.
2. Sin `--create`, termina ahí y ofrece crearlo.
3. Con `--create` (o si el usuario lo pide después):
   - Si la rama no está en el remoto o va por delante, confirma antes de `git push -u origin <rama>`.
   - GitLab: `glab mr create --source-branch <rama> --target-branch <base> --title "<título>" --description "$(cat <archivo>)"` (+ `--draft` si se pidió).
   - GitHub: `gh pr create --base <base> --title "<título>" --body-file <archivo>` (+ `--draft`).
   - Si ya existe un MR/PR para la rama, ofrece actualizar su descripción (`glab mr update <id> --description ...` / `gh pr edit <n> --body-file ...`) en vez de crear otro.
   - Si falta `glab`/`gh` o no hay sesión, entrega el archivo y el link de creación del remoto.
4. Muestra el link del MR/PR creado.
