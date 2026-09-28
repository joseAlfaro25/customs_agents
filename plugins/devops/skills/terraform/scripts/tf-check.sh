#!/usr/bin/env bash
# Verificación estática de una raíz o módulo de Terraform/OpenTofu.
# No usa el backend, no lee ni modifica estado y no llama a APIs de la nube.
#
# Uso: tf-check.sh [directorio]   (por defecto: directorio actual)
# Variables: TF_BIN=tofu para usar OpenTofu.
# Código de salida: 0 si todo pasa, 1 si alguna verificación falla.
set -uo pipefail

dir="${1:-.}"
if [[ ! -d "$dir" ]]; then
  echo "error: '$dir' no es un directorio" >&2
  exit 2
fi
cd "$dir" || exit 2

if ! ls ./*.tf >/dev/null 2>&1; then
  echo "error: no hay archivos .tf en $(pwd)" >&2
  exit 2
fi

tf="${TF_BIN:-terraform}"
if ! command -v "$tf" >/dev/null 2>&1; then
  echo "error: '$tf' no está en el PATH" >&2
  exit 2
fi

failed=0
run() {
  local name="$1"; shift
  echo "==> $name"
  if "$@"; then
    echo "    ok"
  else
    echo "    FALLÓ: $name"
    failed=1
  fi
}

run "fmt -check" "$tf" fmt -check -recursive -diff
# -backend=false: descarga providers/módulos sin inicializar el estado remoto
run "init (sin backend)" "$tf" init -backend=false -input=false -no-color
run "validate" "$tf" validate -no-color

if command -v tflint >/dev/null 2>&1; then
  if [[ -f .tflint.hcl ]]; then
    run "tflint --init" tflint --init
  fi
  run "tflint" tflint --recursive
else
  echo "==> tflint no instalado (omitido)"
fi

if command -v checkov >/dev/null 2>&1; then
  run "checkov" checkov -d . --framework terraform --quiet --compact
elif command -v trivy >/dev/null 2>&1; then
  run "trivy config" trivy config --severity HIGH,CRITICAL --exit-code 1 .
else
  echo "==> checkov/trivy no instalados (omitido)"
fi

if [[ $failed -eq 0 ]]; then
  echo "Todas las verificaciones pasaron."
else
  echo "Hay verificaciones fallidas."
fi
exit $failed
