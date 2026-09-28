#!/usr/bin/env python3
"""Lista las rutas de un proyecto Next.js App Router.

Uso:
    list-routes.py [directorio-del-proyecto]

Busca app/ o src/app/, recorre los segmentos y muestra cada URL con los
archivos especiales presentes (page, layout, loading, error, not-found, route...).
Ignora route groups "(grupo)" y carpetas privadas "_carpeta" en la URL,
marca slots paralelos "@slot" y rutas interceptadas.
"""

from __future__ import annotations

import os
import sys

EXTENSIONS = (".tsx", ".ts", ".jsx", ".js", ".mdx")
SPECIAL = (
    "page",
    "route",
    "layout",
    "template",
    "loading",
    "error",
    "global-error",
    "not-found",
    "forbidden",
    "unauthorized",
    "default",
)
SKIP_DIRS = {"node_modules", ".next", ".git"}


def find_app_dir(root: str) -> str | None:
    for candidate in ("src/app", "app"):
        path = os.path.join(root, candidate)
        if os.path.isdir(path):
            return path
    return None


def special_files(directory: str) -> list[str]:
    found = []
    try:
        entries = os.listdir(directory)
    except OSError:
        return found
    for name in SPECIAL:
        if any(f"{name}{ext}" in entries for ext in EXTENSIONS):
            found.append(name)
    return found


def to_url(segments: list[str]) -> tuple[str, list[str]]:
    parts: list[str] = []
    notes: list[str] = []
    for seg in segments:
        if seg.startswith("(") and seg.endswith(")"):
            continue  # route group
        if seg.startswith("@"):
            notes.append(f"slot {seg}")
            continue
        if seg.startswith("(.") or seg.startswith("(..") or seg.startswith("(..."):
            notes.append(f"intercepta {seg}")
        parts.append(seg)
    return "/" + "/".join(parts), notes


def main() -> int:
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
    app_dir = find_app_dir(root)
    if not app_dir:
        print(f"No se encontró app/ ni src/app/ en {root}", file=sys.stderr)
        return 1

    rows: list[tuple[str, str, str]] = []
    for current, dirs, _files in os.walk(app_dir):
        rel = os.path.relpath(current, app_dir)
        segments = [] if rel == "." else rel.split(os.sep)
        # carpetas privadas: no enrutables, no descender
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("_"))
        files = special_files(current)
        if not files:
            continue
        url, notes = to_url(segments)
        kind = "route handler" if "route" in files else ("page" if "page" in files else "-")
        extra = f"  [{', '.join(notes)}]" if notes else ""
        rows.append((url, kind, ", ".join(files) + extra))

    if not rows:
        print("No se encontraron archivos especiales en", app_dir)
        return 0

    rows.sort(key=lambda r: (r[0], r[1]))
    width = max(len(r[0]) for r in rows)
    print(f"App dir: {os.path.relpath(app_dir, root)}\n")
    print(f"{'URL'.ljust(width)}  {'TIPO'.ljust(13)}  ARCHIVOS")
    for url, kind, files in rows:
        print(f"{url.ljust(width)}  {kind.ljust(13)}  {files}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
