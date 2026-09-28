#!/usr/bin/env bash
# PostToolUse hook: formatea con el Prettier local del proyecto el archivo recién escrito/editado.
# Silencioso y no bloqueante: cualquier fallo se ignora y siempre termina con exit 0.

input="$(cat 2>/dev/null)"

file_path="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print((data.get("tool_input") or {}).get("file_path") or "")
except Exception:
    print("")
' 2>/dev/null)"

[ -z "$file_path" ] && exit 0
[ -f "$file_path" ] || exit 0

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx|*.json) ;;
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

[ -z "$prettier" ] && exit 0

(cd "$dir" && "$prettier" --write --log-level silent "$file_path") >/dev/null 2>&1 || true

exit 0
