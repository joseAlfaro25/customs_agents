#!/usr/bin/env python3
"""Pinnea `uses: owner/repo[/path]@ref` a SHA de commit usando `gh api`.

Uso:
  pin-actions.py [RUTA ...]          # muestra los cambios propuestos (dry-run)
  pin-actions.py --write [RUTA ...]  # reescribe los archivos

RUTA puede ser un archivo .yml/.yaml o un directorio (por defecto .github).
Ignora actions locales (./...), docker:// y refs que ya son SHA de 40 caracteres.
Conserva la versión como comentario: `uses: actions/checkout@<sha> # v7.0.1`.
Requiere GitHub CLI (`gh`) autenticado.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

USES_RE = re.compile(
    r"^(?P<prefix>\s*-?\s*uses:\s*)(?P<q>['\"]?)"
    r"(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^@\s'\"]+)?)@(?P<ref>[^\s'\"#]+)"
    r"(?P=q)(?P<rest>.*)$"
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

_cache: dict[tuple[str, str], str | None] = {}


def resolve(repo: str, ref: str) -> str | None:
    key = (repo, ref)
    if key not in _cache:
        proc = subprocess.run(
            ["gh", "api", f"repos/{repo}/commits/{ref}", "--jq", ".sha"],
            capture_output=True,
            text=True,
        )
        sha = proc.stdout.strip()
        _cache[key] = sha if proc.returncode == 0 and SHA_RE.match(sha) else None
    return _cache[key]


def iter_files(paths: list[str]):
    for p in map(Path, paths):
        if p.is_dir():
            yield from sorted(x for x in p.rglob("*") if x.suffix in (".yml", ".yaml"))
        elif p.is_file():
            yield p


def process(path: Path, write: bool) -> int:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = 0
    for i, line in enumerate(lines):
        m = USES_RE.match(line.rstrip("\n"))
        if not m or SHA_RE.match(m["ref"]):
            continue
        action, ref = m["action"], m["ref"]
        repo = "/".join(action.split("/")[:2])
        sha = resolve(repo, ref)
        if sha is None:
            print(f"{path}:{i + 1}: no se pudo resolver {action}@{ref}", file=sys.stderr)
            continue
        new = f"{m['prefix']}{action}@{sha} # {ref}\n"
        print(f"{path}:{i + 1}: {action}@{ref} -> {sha}")
        lines[i] = new
        changed += 1
    if write and changed:
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", default=[".github"])
    parser.add_argument("--write", action="store_true", help="reescribe los archivos")
    args = parser.parse_args()

    if shutil.which("gh") is None:
        print("error: se requiere GitHub CLI (gh) autenticado", file=sys.stderr)
        return 2

    total = sum(process(f, args.write) for f in iter_files(args.paths))
    mode = "reescritas" if args.write else "por pinnear (usa --write para aplicar)"
    print(f"{total} referencias {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
