#!/usr/bin/env python3
"""Sube la versión de toda la suite (plugins de Claude y Codex + marketplace) en un solo paso.

Uso: python3 scripts/bump-version.py [patch|minor|major|X.Y.Z]   (por defecto: patch)

Súbela antes de publicar cambios: Claude Code y Codex cachean los plugins por versión.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def bump(version: str, part: str) -> str:
    if re.fullmatch(r"\d+\.\d+\.\d+", part):
        return part
    major, minor, patch = map(int, version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    sys.exit(f"Parte inválida: {part} (usa patch, minor, major o X.Y.Z)")


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "patch"
    manifests = sorted(ROOT.glob("plugins/*/.claude-plugin/plugin.json")) + sorted(ROOT.glob("plugins/*/.codex-plugin/plugin.json"))
    current = max((json.loads(p.read_text())["version"] for p in manifests), key=lambda v: tuple(map(int, v.split("."))))
    new = bump(current, part)
    for path in manifests:
        data = json.loads(path.read_text())
        data["version"] = new
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    market = ROOT / ".claude-plugin" / "marketplace.json"
    data = json.loads(market.read_text())
    data.setdefault("metadata", {})["version"] = new
    market.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"{current} → {new} en {len(manifests)} manifiestos + marketplace")


if __name__ == "__main__":
    main()
