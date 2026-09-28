#!/usr/bin/env python3
"""Detecta el stack de un repositorio. Solo lectura. Uso: detect_stack.py [ruta]"""
import json
import re
import sys
from pathlib import Path

SKIP = {"node_modules", ".git", ".venv", "venv", "dist", "build", ".next", ".expo",
        "__pycache__", ".turbo", "coverage", ".terraform", "ios", "android"}
MAX_DEPTH = 4

NODE_TECH = {
    "next": "Next.js", "react": "React", "react-native": "React Native", "expo": "Expo",
    "expo-router": "Expo Router", "typescript": "TypeScript", "@nestjs/core": "NestJS",
    "prisma": "Prisma", "@prisma/client": "Prisma", "typeorm": "TypeORM",
    "tailwindcss": "Tailwind CSS", "@tanstack/react-query": "TanStack Query",
    "zustand": "Zustand", "zod": "Zod", "langchain": "LangChain (JS)",
    "@langchain/core": "LangChain (JS)", "@langchain/langgraph": "LangGraph (JS)",
    "langsmith": "LangSmith (JS)",
}
NODE_TEST = {
    "vitest": "Vitest", "jest": "Jest", "jest-expo": "jest-expo",
    "@testing-library/react": "React Testing Library",
    "@testing-library/react-native": "RN Testing Library",
    "@playwright/test": "Playwright", "cypress": "Cypress", "supertest": "Supertest",
    "detox": "Detox",
}
PY_TECH = {
    "fastapi": "FastAPI", "pydantic": "Pydantic", "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic", "langchain": "LangChain", "langchain-core": "LangChain",
    "langgraph": "LangGraph", "langsmith": "LangSmith", "django": "Django", "flask": "Flask",
}
PY_TEST = {"pytest": "pytest", "pytest-asyncio": "pytest-asyncio", "httpx": "httpx"}
SCRIPT_KEYS = ("dev", "start", "build", "test", "lint", "typecheck", "type-check", "format", "e2e")


def walk(root: Path):
    stack = [(root, 0)]
    while stack:
        d, depth = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_dir():
                if e.name not in SKIP and not e.name.startswith(".") or e.name in (".github",):
                    if depth < MAX_DEPTH:
                        stack.append((e, depth + 1))
            else:
                yield e


def package_manager(d: Path, pkg: dict, root: Path) -> str:
    """packageManager o lockfile, subiendo hasta la raíz (monorepos)."""
    while True:
        pm = pkg.get("packageManager", "")
        if pm:
            return pm.split("@")[0]
        for f, name in (("pnpm-lock.yaml", "pnpm"), ("bun.lock", "bun"), ("bun.lockb", "bun"),
                        ("yarn.lock", "yarn"), ("package-lock.json", "npm")):
            if (d / f).exists():
                return name
        if d == root or d.parent == d:
            return "?"
        d = d.parent
        try:
            pkg = json.loads((d / "package.json").read_text())
        except (OSError, ValueError):
            pkg = {}


def py_deps(path: Path) -> dict:
    text = path.read_text(errors="ignore")
    deps = {}
    for m in re.finditer(r'["\']?([A-Za-z0-9_.\-\[\]]+)\s*([<>=~!^][^"\',\n]*)?["\']?', text):
        name = re.sub(r"\[.*\]", "", m.group(1)).lower()
        if name in PY_TECH or name in PY_TEST:
            deps.setdefault(name, (m.group(2) or "").strip() or "*")
    return deps


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    files = list(walk(root))
    rel = lambda p: str(p.relative_to(root)) or "."
    out = [f"# Stack detectado en {root}"]

    for pj in sorted((f for f in files if f.name == "package.json"), key=lambda f: (len(f.parts), str(f))):
        try:
            pkg = json.loads(pj.read_text())
        except (OSError, ValueError):
            continue
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        tech = sorted({f"{v}@{deps[k]}" for k, v in NODE_TECH.items() if k in deps})
        tests = sorted({f"{v}@{deps[k]}" for k, v in NODE_TEST.items() if k in deps})
        scripts = {k: v for k, v in pkg.get("scripts", {}).items() if k in SCRIPT_KEYS}
        ws = "workspaces" in pkg or (pj.parent / "pnpm-workspace.yaml").exists()
        out.append(f"\n## Node · {rel(pj.parent)} ({pkg.get('name', 'sin nombre')})"
                   + (" · raíz de monorepo" if ws else ""))
        out.append(f"- Gestor: {package_manager(pj.parent, pkg, root)}")
        if tech:
            out.append(f"- Tecnologías: {', '.join(tech)}")
        if tests:
            out.append(f"- Tests: {', '.join(tests)}")
        for k, v in scripts.items():
            out.append(f"- script `{k}`: {v}")

    for pf in sorted(f for f in files if f.name == "pyproject.toml" or re.match(r"requirements.*\.txt$", f.name)):
        deps = py_deps(pf)
        if not deps:
            continue
        d = pf.parent
        mgr = "uv" if (d / "uv.lock").exists() else "poetry" if (d / "poetry.lock").exists() else "pip"
        out.append(f"\n## Python · {rel(pf)}")
        out.append(f"- Gestor: {mgr}")
        tech = [f"{PY_TECH[k]} {v}" for k, v in deps.items() if k in PY_TECH]
        tests = [f"{PY_TEST[k]} {v}" for k, v in deps.items() if k in PY_TEST]
        if tech:
            out.append(f"- Tecnologías: {', '.join(sorted(set(tech)))}")
        if tests:
            out.append(f"- Tests: {', '.join(tests)}")

    names = {f.name for f in files}
    paths = [rel(f) for f in files]
    infra = []
    if any(n.startswith("Dockerfile") for n in names):
        infra.append("Docker")
    if any(re.match(r"(docker-)?compose.*\.ya?ml$", n) for n in names):
        infra.append("Docker Compose")
    if any(p.startswith(".github/workflows/") for p in paths):
        infra.append("GitHub Actions")
    if "Chart.yaml" in names:
        infra.append("Helm")
    if "kustomization.yaml" in names:
        infra.append("Kustomize")
    if any(n.endswith(".tf") for n in names):
        infra.append("Terraform")
    if "eas.json" in names:
        infra.append("EAS (Expo)")
    if "langgraph.json" in names:
        infra.append("LangGraph Platform config")
    if infra:
        out.append("\n## Infra / despliegue\n- " + ", ".join(infra))

    ctx = [p for p in paths if Path(p).name in ("CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md")]
    adr = [p for p in paths if "/adr/" in f"/{p}"]
    if ctx or adr:
        out.append("\n## Documentos de contexto")
        out += [f"- {p}" for p in ctx]
        if adr:
            out.append(f"- ADRs: {len(adr)} archivos en {Path(adr[0]).parent}")

    if len(out) == 1:
        out.append("\nNo se detectaron manifiestos conocidos.")
    print("\n".join(out))


if __name__ == "__main__":
    main()
