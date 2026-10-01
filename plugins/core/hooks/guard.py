#!/usr/bin/env python3
"""PreToolUse guard: pide confirmación al usuario antes de editar archivos de
secretos o ejecutar comandos destructivos.

- Claude Code (por defecto): responde "ask" → el usuario confirma o rechaza.
- Codex (`--codex`): Codex no soporta "ask", así que responde "deny" con el motivo;
  también revisa los archivos tocados por `apply_patch`.

Nunca falla: ante cualquier error, deja pasar la acción."""

import json
import re
import sys
from pathlib import PurePath

SECRET_FILE = re.compile(
    r"(^|/)(\.env(\.(?!example$|sample$|template$)[\w.-]+)?|.*\.pem|.*\.key|id_(rsa|ed25519|ecdsa)"
    r"|.*\.p12|.*\.pfx|credentials\.json|service-account.*\.json|\.npmrc|\.pypirc)$"
)
DANGEROUS = [
    (
        r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*\s+(/|~|\$HOME)(\s|$)",
        "borrado recursivo de / o del home",
    ),
    (r"\bgit\s+push\b(?=.*(--force(?!-with-lease)|\s-f\b))", "git push --force"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard (descarta cambios)"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f", "git clean (borra archivos no versionados)"),
    (r"\bterraform\s+(apply|destroy)\b", "terraform apply/destroy"),
    (r"\bkubectl\s+(apply|delete|replace|drain|scale)\b", "kubectl sobre un cluster"),
    (r"\baws\s+s3\s+(rm|rb|mv|sync)\b", "aws s3 que borra, mueve o sincroniza objetos"),
    (
        r"\baws\b[^|;&\n]*?\s(create|delete|put|update|terminate|modify|attach|detach|revoke|authorize|remove"
        r"|deregister|register|run|stop|reboot|disable|enable|release|associate|disassociate|restore|reset"
        r"|rotate|schedule|tag|untag|purge|publish)-[a-z0-9-]+",
        "aws CLI que crea, modifica o borra recursos",
    ),
    (r"\baws\s+lambda\s+invoke\b", "aws lambda invoke (ejecuta código en la nube)"),
    (
        r"\bgcloud\s+(?!components\b)[^|;&\n]*?\b(create|delete|update|deploy|enable|disable|resize|restore|reset"
        r"|stop|submit|set-iam-policy|add-iam-policy-binding|remove-iam-policy-binding)\b",
        "gcloud que crea, modifica o borra recursos",
    ),
    (
        r"\b(gcloud\s+storage|gsutil)\s+(rm|mv|rsync)\b",
        "gcloud storage/gsutil que borra, mueve o sincroniza objetos",
    ),
    (r"\bhelm\s+(install|upgrade|uninstall|delete)\b", "helm sobre un cluster"),
    (r"\bdocker\s+(push|system\s+prune)\b", "docker push/prune"),
    (
        r"\beas\s+(build|submit|update)\b",
        "EAS build/submit/update (servicio de pago/público)",
    ),
    (r"\b(DROP\s+(TABLE|DATABASE)|TRUNCATE)\b", "SQL destructivo"),
]


CODEX = "--codex" in sys.argv
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def ask(reason: str) -> None:
    if CODEX:
        decision, suffix = (
            "deny",
            (
                "Bloqueado por seguridad: pide confirmación explícita al usuario "
                "y, si la da, que lo ejecute él mismo"
            ),
        )
    else:
        decision, suffix = "ask", "Confirma si quieres continuar"
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": f"[core guard] {reason}. {suffix}.",
                }
            }
        )
    )


def edited_paths(tin: dict) -> list:
    paths = [str(tin["file_path"])] if tin.get("file_path") else []
    for value in tin.values():  # apply_patch de Codex: rutas dentro del parche
        if isinstance(value, str):
            paths += [m.strip() for m in PATCH_FILE.findall(value)]
    return paths


def main() -> None:
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tin = data.get("tool_input", {}) or {}

    if tool in ("Write", "Edit", "MultiEdit", "apply_patch"):
        for path in edited_paths(tin):
            if SECRET_FILE.search(PurePath(path).as_posix()):
                ask(f"Vas a modificar un archivo de secretos o credenciales: {path}")
                return
        return

    if tool == "Bash":
        cmd = str(tin.get("command", ""))
        for pattern, label in DANGEROUS:
            if re.search(pattern, cmd, re.IGNORECASE):
                ask(
                    f"Comando potencialmente destructivo o que afecta entornos reales ({label})"
                )
                return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
