#!/usr/bin/env bash
# PostToolUse hook: formatea con el prettier local del proyecto el archivo
# escrito/editado. Silencioso y nunca bloquea: siempre termina con exit 0.

input="$(cat 2>/dev/null)"

command -v python3 >/dev/null 2>&1 || exit 0

file_path="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print((data.get("tool_input") or {}).get("file_path") or "")
except Exception:
    pass
' 2>/dev/null)"

[ -n "$file_path" ] || exit 0
[ -f "$file_path" ] || exit 0

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx|*.json|*.css|*.md|*.mdx) ;;
  *) exit 0 ;;
esac

# Busca node_modules/.bin/prettier subiendo desde el directorio del archivo.
dir="$(cd "$(dirname "$file_path")" 2>/dev/null && pwd)" || exit 0
prettier=""
while [ -n "$dir" ]; do
  if [ -x "$dir/node_modules/.bin/prettier" ]; then
    prettier="$dir/node_modules/.bin/prettier"
    break
  fi
  [ "$dir" = "/" ] && break
  dir="$(dirname "$dir")"
done

[ -n "$prettier" ] || exit 0

# Ejecuta desde la raíz donde está prettier para que resuelva su config e ignore.
(cd "$dir" && "$prettier" --write --ignore-unknown "$file_path") >/dev/null 2>&1 || true

exit 0
