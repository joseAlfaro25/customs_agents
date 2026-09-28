#!/usr/bin/env bash
# Hook PostToolUse (Write|Edit|MultiEdit): ejecuta `terraform fmt` sobre archivos .tf/.tfvars.
# Lee el JSON del evento por stdin. Silencioso y nunca bloquea: siempre exit 0.

input="$(cat 2>/dev/null)" || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

file_path="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print((data.get("tool_input") or {}).get("file_path") or "")
except Exception:
    pass
' 2>/dev/null)" || exit 0

[ -n "$file_path" ] || exit 0
case "$file_path" in
  *.tf|*.tfvars) ;;
  *) exit 0 ;;
esac
[ -f "$file_path" ] || exit 0
command -v terraform >/dev/null 2>&1 || exit 0

terraform fmt "$file_path" >/dev/null 2>&1 || true
exit 0
