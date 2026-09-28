#!/usr/bin/env bash
# My Agents — instalador de un solo comando.
#
# Detecta las IAs instaladas (Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot) e instala
# en cada una toda la suite: agentes, skills, comandos, hooks e información general.
#
#   curl -fsSL https://raw.githubusercontent.com/joseAlfaro25/customs_agents/main/install.sh | bash
#   ./install.sh                                   # desde un clon del repo
#   ./install.sh --tools claude,codex              # solo algunas herramientas
#   ./install.sh --project ~/mi-app                # además: AGENTS.md + Copilot en ese proyecto
#   ./install.sh --uninstall                       # quitar todo
#
# Volver a ejecutarlo actualiza la suite (es idempotente).
set -euo pipefail

REPO_URL="${MY_AGENTS_REPO:-https://github.com/joseAlfaro25/customs_agents.git}"
INSTALL_DIR="${MY_AGENTS_HOME:-$HOME/.local/share/my-agents}"
MARKETPLACE="my-agents"
PLUGINS=(core frontend backend devops mobile)

TOOLS=""
PROJECT=""
UNINSTALL=0
DRY_RUN=0

usage() {
  sed -n '2,13p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Opciones:
  --tools LISTA     claude,codex,cursor,gemini,copilot (por defecto: las que detecte)
  --project DIR     Exporta también a ese proyecto: AGENTS.md, .agents/skills y GitHub Copilot
  --uninstall       Desinstala la suite de todas las herramientas indicadas/detectadas
  --dry-run         Muestra los comandos sin ejecutarlos
  -h, --help        Esta ayuda

Variables: MY_AGENTS_REPO (repo git), MY_AGENTS_HOME (dónde clonar; por defecto ~/.local/share/my-agents)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tools) TOOLS="${2:?--tools requiere una lista}"; shift 2 ;;
    --project) PROJECT="${2:?--project requiere un directorio}"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; usage; exit 2 ;;
  esac
done

# ------------------------------------------------------------------------------ utilidades
if [[ -t 1 ]]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'; else B=""; G=""; Y=""; R=""; N=""; fi
step() { printf '\n%s==> %s%s\n' "$B" "$*" "$N"; }
ok()   { printf '  %s✔%s %s\n' "$G" "$N" "$*"; }
warn() { printf '  %s!%s %s\n' "$Y" "$N" "$*"; }
fail() { printf '%s✖ %s%s\n' "$R" "$*" "$N" >&2; exit 1; }
run()  { if [[ $DRY_RUN -eq 1 ]]; then printf '  + %s\n' "$*" >&2; else "$@"; fi; }
# Ejecuta sin abortar el script si falla (para pasos idempotentes: "ya existe", "no instalado"...)
try()  { if [[ $DRY_RUN -eq 1 ]]; then printf '  + %s\n' "$*" >&2; else "$@" >/dev/null 2>&1 || return 1; fi; }
has()  { command -v "$1" >/dev/null 2>&1; }
want() { [[ ",$SELECTED," == *",$1,"* ]]; }

# ------------------------------------------------------------------------------ fuente de la suite
script_dir() {
  if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
  fi
}

resolve_source() {
  local here
  here="$(script_dir)"
  if [[ -n "$here" && -f "$here/.claude-plugin/marketplace.json" ]]; then
    SRC="$here"
    ok "Usando el repo local: $SRC"
    return
  fi
  has git || fail "Se necesita git para descargar la suite."
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    run git -C "$INSTALL_DIR" pull --ff-only --quiet
    ok "Suite actualizada en $INSTALL_DIR"
  else
    run git clone --depth 1 --quiet "$REPO_URL" "$INSTALL_DIR"
    ok "Suite descargada en $INSTALL_DIR"
  fi
  SRC="$INSTALL_DIR"
}

export_py() { run python3 "$SRC/scripts/export.py" "$@"; }

# ------------------------------------------------------------------------------ Claude Code
install_claude() {
  step "Claude Code"
  if claude plugin marketplace list 2>/dev/null | grep -q "$MARKETPLACE"; then
    try claude plugin marketplace update "$MARKETPLACE" && ok "Marketplace actualizado" || warn "No se pudo actualizar el marketplace"
  else
    run claude plugin marketplace add "$SRC" >/dev/null && ok "Marketplace '$MARKETPLACE' agregado"
  fi
  local updating=0
  if claude plugin list 2>/dev/null | grep -q "suite@$MARKETPLACE"; then
    # Reinstalar asegura la última versión aunque no se haya subido el número de versión
    updating=1
    try claude plugin uninstall "suite@$MARKETPLACE" --prune -y || true
    for p in "${PLUGINS[@]}"; do try claude plugin uninstall "$p@$MARKETPLACE" || true; done
  fi
  run claude plugin install "suite@$MARKETPLACE" --scope user >/dev/null
  if [[ $updating -eq 1 ]]; then
    ok "Plugins actualizados (reinicia Claude Code para aplicar)"
  else
    ok "Instalado suite@$MARKETPLACE → core, frontend, backend, devops, mobile"
  fi
}

uninstall_claude() {
  step "Claude Code"
  try claude plugin uninstall "suite@$MARKETPLACE" --prune -y && ok "Plugins desinstalados" || warn "suite no estaba instalado"
  for p in "${PLUGINS[@]}"; do try claude plugin uninstall "$p@$MARKETPLACE" || true; done
  try claude plugin marketplace remove "$MARKETPLACE" && ok "Marketplace eliminado" || true
}

# ------------------------------------------------------------------------------ Codex
install_codex() {
  step "Codex"
  if ! codex plugin marketplace list 2>/dev/null | grep -q "$MARKETPLACE"; then
    run codex plugin marketplace add "$SRC" >/dev/null && ok "Marketplace '$MARKETPLACE' agregado"
  else
    try codex plugin marketplace upgrade "$MARKETPLACE" || true
    ok "Marketplace ya configurado"
  fi
  for p in "${PLUGINS[@]}"; do
    try codex plugin remove "$p@$MARKETPLACE" || true   # reinstalar = refrescar la copia en caché
    run codex plugin add "$p@$MARKETPLACE" >/dev/null
  done
  ok "Plugins (skills + hook de seguridad): ${PLUGINS[*]}"
  export_py --target codex --user --skip-skills >/dev/null
  ok "Agentes en ${CODEX_HOME:-~/.codex}/agents, comandos (\$feature, \$review...) y AGENTS.md global"
}

uninstall_codex() {
  step "Codex"
  for p in "${PLUGINS[@]}"; do try codex plugin remove "$p@$MARKETPLACE" || true; done
  try codex plugin marketplace remove "$MARKETPLACE" || true
  export_py --target codex --user --uninstall >/dev/null
  ok "Plugins, agentes, comandos y bloque de AGENTS.md eliminados"
}

# ------------------------------------------------------------------------------ Cursor / Gemini (export a nivel usuario)
install_export_user() {  # $1=target $2=nombre
  step "$2"
  export_py --target "$1" --user >/dev/null
  case "$1" in
    cursor) ok "Skills, agentes y comandos en ~/.cursor (AGENTS.md se agrega por proyecto con --project)" ;;
    gemini) ok "Skills, agentes y comandos en ~/.gemini y bloque en ~/.gemini/GEMINI.md" ;;
  esac
}

uninstall_export_user() {
  step "$2"
  export_py --target "$1" --user --uninstall >/dev/null
  ok "Eliminado"
}

# ------------------------------------------------------------------------------ Proyecto (AGENTS.md, Copilot, genérico)
project_targets() {
  local t="agents"
  want copilot && t="$t,copilot"
  echo "$t"
}

install_project() {
  step "Proyecto $PROJECT"
  [[ -d "$PROJECT" ]] || fail "No existe el directorio: $PROJECT"
  export_py --target "$(project_targets)" --dest "$PROJECT" >/dev/null
  ok "AGENTS.md + .agents/skills$(want copilot && echo ' + .github/{agents,skills,prompts} (Copilot)')"
}

uninstall_project() {
  step "Proyecto $PROJECT"
  export_py --target "$(project_targets)" --dest "$PROJECT" --uninstall >/dev/null
  ok "Eliminado del proyecto"
}

# ------------------------------------------------------------------------------ main
main() {
  printf '%sMy Agents%s — suite de agentes y skills para frontend, backend, IA, devops y mobile\n' "$B" "$N"
  has python3 || fail "Se necesita python3."

  if [[ -z "$TOOLS" ]]; then
    local detected=()
    has claude && detected+=(claude)
    has codex && detected+=(codex)
    { has cursor-agent || has cursor || [[ -d "$HOME/.cursor" ]]; } && detected+=(cursor)
    { has gemini || [[ -d "$HOME/.gemini" ]]; } && detected+=(gemini)
    { has copilot || [[ -n "$PROJECT" && -d "$PROJECT/.github" ]]; } && detected+=(copilot)
    SELECTED="$(IFS=,; echo "${detected[*]:-}")"
  else
    SELECTED="$TOOLS"
  fi
  [[ -n "$SELECTED" || -n "$PROJECT" ]] || fail "No se detectó ninguna herramienta. Usa --tools o --project."
  echo "Herramientas: ${SELECTED:-ninguna}${PROJECT:+ · proyecto: $PROJECT}"

  local action=install
  if [[ $UNINSTALL -eq 0 ]]; then
    step "Descargando la suite"
    resolve_source
  else
    action=uninstall
    SRC="$(script_dir)"
    [[ -n "$SRC" && -f "$SRC/scripts/export.py" ]] || SRC="$INSTALL_DIR"
    [[ -f "$SRC/scripts/export.py" ]] || fail "No encuentro la suite en $SRC para desinstalar."
  fi

  local tool
  for tool in claude codex; do
    if want "$tool"; then
      if has "$tool"; then "${action}_${tool}"; else warn "$tool no está instalado; omitido"; fi
    fi
  done
  if want cursor; then "${action}_export_user" cursor "Cursor"; fi
  if want gemini; then "${action}_export_user" gemini "Gemini CLI"; fi
  if want copilot && [[ -z "$PROJECT" ]]; then
    warn "Copilot se instala por proyecto: vuelve a ejecutar con --project <dir>"
  fi
  if [[ -n "$PROJECT" ]]; then "${action}_project"; fi

  step "Listo"
  if [[ $UNINSTALL -eq 0 ]]; then
    echo "  Empieza con: /feature <descripción> (Claude, Cursor, Copilot, Gemini) o \$feature <descripción> (Codex)."
    echo "  Para actualizar, vuelve a ejecutar este mismo comando."
  fi
}

main
