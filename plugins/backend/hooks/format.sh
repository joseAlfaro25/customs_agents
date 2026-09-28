#!/usr/bin/env bash
# PostToolUse hook: formatea el archivo editado.
#  - .py            -> ruff format + ruff check --fix (ruff en .venv del proyecto o en PATH).
#                      F401 no se autocorrige para no borrar imports recién añadidos.
#  - .ts/.js/.json  -> prettier desde node_modules/.bin (buscando hacia arriba)
# Nunca falla ni bloquea: salida silenciosa y exit 0 siempre.

{
  command -v python3 >/dev/null 2>&1 || exit 0

  input="$(cat)"
  file_path="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print((data.get("tool_input") or {}).get("file_path") or "")
except Exception:
    print("")
' 2>/dev/null)"

  [ -n "$file_path" ] || exit 0
  [ -f "$file_path" ] || exit 0

  dir="$(cd "$(dirname "$file_path")" 2>/dev/null && pwd)" || exit 0

  # Busca hacia arriba desde el directorio del archivo un path relativo ejecutable.
  find_up() {
    local d="$dir" rel="$1"
    while [ -n "$d" ]; do
      if [ -x "$d/$rel" ]; then
        printf '%s\n' "$d/$rel"
        return 0
      fi
      [ "$d" = "/" ] && break
      d="$(dirname "$d")"
    done
    return 1
  }

  case "$file_path" in
    *.py)
      ruff_bin="$(find_up ".venv/bin/ruff" || find_up "venv/bin/ruff" || command -v ruff || true)"
      if [ -n "$ruff_bin" ]; then
        (cd "$dir" && "$ruff_bin" format --quiet "$file_path"; "$ruff_bin" check --fix --unfixable F401 --quiet "$file_path")
      fi
      ;;
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.mts|*.cts|*.json)
      prettier_bin="$(find_up "node_modules/.bin/prettier" || true)"
      if [ -n "$prettier_bin" ]; then
        (cd "$dir" && "$prettier_bin" --write "$file_path")
      fi
      ;;
  esac
} >/dev/null 2>&1

exit 0
