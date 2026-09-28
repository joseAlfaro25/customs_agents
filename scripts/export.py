#!/usr/bin/env python3
"""Exporta la suite My Agents (fuente: plugins/, formato Claude Code) a otras herramientas de IA.

Targets:
  codex    .codex/agents/*.toml · .agents/skills/ (skills + comandos como skills) · AGENTS.md
  cursor   .cursor/agents/*.md · .cursor/skills/ · .cursor/commands/*.md · AGENTS.md
  copilot  .github/agents/*.agent.md · .github/skills/ · .github/prompts/*.prompt.md · AGENTS.md
  gemini   .gemini/agents/*.md · .gemini/skills/ · .gemini/commands/*.toml · GEMINI.md
  agents   .agents/skills/ (skills + agentes y comandos como skills) · AGENTS.md
           (genérico: cualquier herramienta compatible con Agent Skills y AGENTS.md)

Uso:
  python3 scripts/export.py --target codex --dest ~/proyectos/mi-app
  python3 scripts/export.py --target cursor,copilot --dest . --plugins core,frontend
  python3 scripts/export.py --target codex --user          # instala en el home (~/.codex, ~/.agents)
  python3 scripts/export.py --target all --dest . --dry-run
  python3 scripts/export.py --target codex --dest . --uninstall

Es idempotente: guarda un manifiesto en <dest>/.my-agents/<target>.json, borra en cada
ejecución lo que generó antes y ya no corresponde, y nunca sobrescribe archivos ajenos
(salvo con --force). En AGENTS.md / GEMINI.md solo reemplaza el bloque entre marcadores.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
PLUGIN_ORDER = ["core", "frontend", "backend", "devops", "mobile"]
TARGETS = ["codex", "cursor", "copilot", "gemini", "agents"]
MARK_START = "<!-- my-agents:start -->"
MARK_END = "<!-- my-agents:end -->"
NAMESPACED = re.compile(r"\b(core|frontend|backend|devops|mobile):([a-z0-9][a-z0-9-]*)")
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Mapeo de herramientas Claude → otras herramientas
COPILOT_TOOLS = {"Read": "read", "Write": "edit", "Edit": "edit", "Glob": "search", "Grep": "search",
                 "Bash": "execute", "WebFetch": "web", "WebSearch": "web"}
GEMINI_TOOLS = {"Read": ["read_file", "read_many_files", "list_directory"], "Write": ["write_file"],
                "Edit": ["replace"], "Glob": ["glob"], "Grep": ["grep_search"], "Bash": ["run_shell_command"],
                "WebFetch": ["web_fetch"], "WebSearch": ["google_web_search"]}

# Directorios por target: (proyecto, usuario). None = no soportado a nivel usuario.
LAYOUT = {
    "codex": {"skills": (".agents/skills", ".agents/skills"), "agents": (".codex/agents", ".codex/agents"),
              "context": ("AGENTS.md", ".codex/AGENTS.md")},
    "cursor": {"skills": (".cursor/skills", ".cursor/skills"), "agents": (".cursor/agents", ".cursor/agents"),
               "commands": (".cursor/commands", ".cursor/commands"), "context": ("AGENTS.md", None)},
    "copilot": {"skills": (".github/skills", ".copilot/skills"), "agents": (".github/agents", ".copilot/agents"),
                "commands": (".github/prompts", None), "context": ("AGENTS.md", None)},
    "gemini": {"skills": (".gemini/skills", ".gemini/skills"), "agents": (".gemini/agents", ".gemini/agents"),
               "commands": (".gemini/commands", ".gemini/commands"), "context": ("GEMINI.md", ".gemini/GEMINI.md")},
    "agents": {"skills": (".agents/skills", ".agents/skills"), "context": ("AGENTS.md", None)},
}


# ---------------------------------------------------------------------------- lectura de la fuente

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Frontmatter YAML simple (clave: valor en una línea), suficiente para esta suite."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.index("\n---", 4)
    meta = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            key, value = line.split(":", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            meta[key.strip()] = value
    return meta, text[end + 4:].lstrip("\n")


@dataclass
class Item:
    plugin: str
    name: str
    meta: dict
    body: str
    path: Path
    tools: list[str] = field(default_factory=list)

    @property
    def readonly(self) -> bool:
        return not (set(self.tools) & WRITE_TOOLS)


def load(plugins: list[str]) -> dict[str, list[Item]]:
    out = {"skills": [], "agents": [], "commands": []}
    for plugin in plugins:
        base = PLUGINS_DIR / plugin
        if not base.is_dir():
            sys.exit(f"Plugin desconocido: {plugin}")
        for skill_md in sorted(base.glob("skills/*/SKILL.md")):
            meta, body = parse_frontmatter(skill_md.read_text())
            out["skills"].append(Item(plugin, meta["name"], meta, body, skill_md.parent))
        for agent in sorted(base.glob("agents/*.md")):
            meta, body = parse_frontmatter(agent.read_text())
            tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
            out["agents"].append(Item(plugin, meta["name"], meta, body, agent, tools))
        for cmd in sorted(base.glob("commands/*.md")):
            meta, body = parse_frontmatter(cmd.read_text())
            out["commands"].append(Item(plugin, cmd.stem, meta, body, cmd))
    return out


# ---------------------------------------------------------------------------- transformaciones

def flatten(text: str) -> str:
    """`core:project-context` → `project-context` (fuera de Claude/Codex los nombres no llevan prefijo)."""
    return NAMESPACED.sub(r"\2", text)


CLAUDE_ONLY = re.compile(r"\n?<!-- claude-only -->.*?<!-- /claude-only -->\n?", re.S)


def strip_claude_only(text: str) -> str:
    return CLAUDE_ONLY.sub("\n", text)


def fix_paths(text: str, skills_dir: str) -> str:
    return re.sub(r"<carpeta de la skill ([a-z0-9-]+)>", lambda m: f"{skills_dir}/{m.group(1)}", text)


def args_placeholder(body: str, target: str) -> str:
    if target == "gemini":
        return body.replace("$ARGUMENTS", "{{args}}")
    return body.replace("$ARGUMENTS", "<argumentos>")


def yaml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)  # JSON string ⊂ YAML


def toml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def toml_multiline(value: str) -> str:
    if "'''" not in value:
        return "'''\n" + value.rstrip() + "\n'''"
    return toml_str(value)


AGENT_PREAMBLE = ("> Agente de la suite My Agents. Las skills mencionadas están instaladas en `{skills}`; "
                  "cárgalas leyendo su `SKILL.md` cuando el flujo lo indique.\n\n")


PLUGIN_PREAMBLE = ("> Agente de la suite My Agents. Las skills mencionadas vienen del plugin My Agents instalado "
                   "(nombres con prefijo, p. ej. `core:project-context`).\n\n")


# ---------------------------------------------------------------------------- escritura

class Writer:
    def __init__(self, dest: Path, target: str, dry_run: bool, force: bool):
        self.dest, self.target, self.dry_run, self.force = dest, target, dry_run, force
        self.manifest_path = dest / ".my-agents" / f"{target}.json"
        self.previous = read_manifest(self.manifest_path)
        # Archivos de otros targets de My Agents en este destino (p. ej. codex y agents comparten .agents/skills)
        self.others = set().union(*(read_manifest(m) for m in (dest / ".my-agents").glob("*.json")
                                    if m != self.manifest_path)) if (dest / ".my-agents").is_dir() else set()
        self.files: set[str] = set()
        self.skipped: list[str] = []

    def write(self, rel: str, content: str | bytes, mode: int | None = None) -> None:
        path = self.dest / rel
        if path.exists() and rel not in self.previous | self.others and not self.force:
            self.skipped.append(rel)
            return
        self.files.add(rel)
        if self.dry_run:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
        if mode:
            path.chmod(mode)

    def copy_tree(self, src: Path, rel_dir: str, transform) -> None:
        for f in sorted(src.rglob("*")):
            if f.is_dir() or f.name == ".DS_Store":
                continue
            rel = f"{rel_dir}/{f.relative_to(src).as_posix()}"
            if f.suffix == ".md":
                self.write(rel, transform(f.read_text()))
            else:
                self.write(rel, f.read_bytes(), f.stat().st_mode & 0o777)

    def context_block(self, rel: str, block: str) -> None:
        path = self.dest / rel
        current = path.read_text() if path.exists() else ""
        section = f"{MARK_START}\n{block.strip()}\n{MARK_END}"
        if MARK_START in current and MARK_END in current:
            new = re.sub(re.escape(MARK_START) + r".*?" + re.escape(MARK_END), lambda _: section, current, flags=re.S)
        else:
            new = (current.rstrip() + "\n\n" if current.strip() else "") + section + "\n"
        self.files.add(f"{rel}#block")
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new)

    def finish(self) -> list[str]:
        stale = sorted(self.previous - self.files - self.others)
        if not self.dry_run:
            for rel in stale:
                remove(self.dest, rel)
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            self.manifest_path.write_text(json.dumps({"target": self.target, "files": sorted(self.files)}, indent=2))
        return stale


def read_manifest(path: Path) -> set[str]:
    try:
        return set(json.loads(path.read_text())["files"])
    except (OSError, ValueError, KeyError):
        return set()


def remove(dest: Path, rel: str) -> None:
    if rel.endswith("#block"):
        path = dest / rel[: -len("#block")]
        if path.exists():
            text = re.sub(r"\n*" + re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + r"\n?", "\n",
                          path.read_text(), flags=re.S).strip()
            path.unlink() if not text else path.write_text(text + "\n")
        return
    path = dest / rel
    if path.exists():
        path.unlink()
        parent = path.parent
        stop = {dest, Path.home(), Path(parent.anchor)}
        while parent not in stop and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent


# ---------------------------------------------------------------------------- contexto (AGENTS.md)

def context_markdown(data: dict[str, list[Item]], user: bool) -> str:
    agent_rows = "\n".join(f"| `{a.name}` | {a.plugin} | {flatten(a.meta['description'])} |" for a in data["agents"])
    skills_by_plugin: dict[str, list[str]] = {}
    for s in data["skills"]:
        skills_by_plugin.setdefault(s.plugin, []).append(f"`{s.name}`")
    skill_rows = "\n".join(f"| {p} | {', '.join(v)} |" for p, v in skills_by_plugin.items())
    home = "~/" if user else ""
    where = (f"`{home}.agents/skills` (Codex y genérico), `{home}.cursor/skills` (Cursor), "
             f"`{home}.github/skills` (Copilot) o `{home}.gemini/skills` (Gemini), según la herramienta que uses")
    skills_dir = "<carpeta de skills>"
    commands = ", ".join(f"`{c.name}`" for c in data["commands"])
    return f"""
## My Agents — instrucciones para agentes de IA

Este proyecto usa la suite **My Agents**: agentes y skills para Next.js, React, TypeScript, NestJS,
FastAPI, LangChain, LangGraph, LangSmith, Docker, GitHub Actions, Kubernetes, Terraform, React Native y Expo.

### Antes de cualquier tarea
1. Lee la skill `project-context` (`{skills_dir}/project-context/SKILL.md`): detecta el stack y sus
   versiones, lee las reglas del proyecto y te dice qué skill y qué agente especialista usar.
2. Las reglas de este archivo y de la documentación del proyecto ganan sobre las convenciones de las skills.
3. Sigue el código existente: estructura, naming, librerías y gestor de paquetes del lockfile.

### Flujo de trabajo
`planner` → `architect` (si hay decisiones de diseño/ADR) → `coder` o especialista de stack → `tester`
→ `reviewer` (+ reviewer del stack) → `documenter`. Para tareas de un solo stack, delega en su especialista.

### Reglas que no se negocian
- Nunca escribas secretos en código, tests, logs ni commits; variables nuevas solo en `.env.example`, sin valor.
- Valida toda entrada externa (incluida la salida de un LLM); SQL parametrizado; autorización en el servidor.
- No instales dependencias, hagas commit/push, despliegues, `terraform apply`, `kubectl apply` ni builds/updates
  de EAS sin confirmación explícita del usuario.
- Antes de terminar: typecheck, lint y tests afectados con los comandos reales del proyecto; reporta el resultado.

### Agentes
| Agente | Plugin | Cuándo usarlo |
|---|---|---|
{agent_rows}

### Skills (en `{skills_dir}/`)
| Plugin | Skills |
|---|---|
{skill_rows}

### Comandos
{commands}.

| Herramienta | Cómo invocarlos |
|---|---|
| Claude Code | `/nombre` (plugins de `.claude-plugin/`) |
| Codex | `$nombre` (instalados como skills) |
| Cursor | `/nombre` (`.cursor/commands/`) |
| GitHub Copilot | `/nombre` (`.github/prompts/`) |
| Gemini CLI | `/nombre` (`.gemini/commands/`) |
| Otras (genérico) | skill `cmd-nombre`; los agentes son skills `agent-nombre` |

Notas:
- `<carpeta de skills>` = {where}. `<carpeta de la skill X>` = `<carpeta de skills>/X`.
- Las referencias con prefijo (`core:project-context`) equivalen al nombre sin prefijo (`project-context`).
"""


# ---------------------------------------------------------------------------- exportadores por target

def export(target: str, data: dict[str, list[Item]], writer: Writer, user: bool, skip_skills: bool) -> None:
    lay = {k: v[1] if user else v[0] for k, v in LAYOUT[target].items()}
    if user and target == "codex" and os.environ.get("CODEX_HOME"):
        codex_home = os.environ["CODEX_HOME"]  # respeta un CODEX_HOME personalizado (rutas absolutas)
        lay["agents"], lay["context"] = f"{codex_home}/agents", f"{codex_home}/AGENTS.md"
    skills_dir = lay["skills"] if not user else f"~/{lay['skills']}"
    if skip_skills:
        # Las skills vienen del plugin nativo (Claude/Codex): se conservan nombres con prefijo y rutas genéricas
        to_text = lambda t: t  # noqa: E731
    else:
        to_text = lambda t: fix_paths(flatten(strip_claude_only(t)), skills_dir)  # noqa: E731
        # Skills: el formato Agent Skills es común a todas las herramientas
        for s in data["skills"]:
            writer.copy_tree(s.path, f"{lay['skills']}/{s.name}", to_text)

    # Agentes
    for a in data["agents"]:
        desc = a.meta["description"] if skip_skills else flatten(a.meta["description"])
        preamble = PLUGIN_PREAMBLE if skip_skills else AGENT_PREAMBLE.format(skills=skills_dir)
        body = preamble + to_text(a.body)
        if target == "codex":
            sandbox = "read-only" if a.readonly else "workspace-write"
            writer.write(f"{lay['agents']}/{a.name}.toml",
                         f"# Generado por My Agents (plugin {a.plugin}). No editar: regenerar con scripts/export.py\n"
                         f"name = {toml_str(a.name)}\ndescription = {toml_str(desc)}\n"
                         f"sandbox_mode = {toml_str(sandbox)}\n"
                         f"developer_instructions = {toml_multiline(body)}\n")
        elif target == "cursor":
            writer.write(f"{lay['agents']}/{a.name}.md",
                         f"---\nname: {a.name}\ndescription: {yaml_str(desc)}\nmodel: inherit\n"
                         f"readonly: {'true' if a.readonly else 'false'}\n---\n\n{body}")
        elif target == "copilot":
            tools = sorted({COPILOT_TOOLS[t] for t in a.tools if t in COPILOT_TOOLS} | {"todo"})
            writer.write(f"{lay['agents']}/{a.name}.agent.md",
                         f"---\nname: {a.name}\ndescription: {yaml_str(desc)}\n"
                         f"tools: [{', '.join(yaml_str(t) for t in tools)}]\n---\n\n{body}")
        elif target == "gemini":
            tools = [g for t in a.tools for g in GEMINI_TOOLS.get(t, [])]
            tools = list(dict.fromkeys(tools))
            tool_yaml = "".join(f"\n  - {t}" for t in tools)
            writer.write(f"{lay['agents']}/{a.name}.md",
                         f"---\nname: {a.name}\ndescription: {yaml_str(desc)}\nkind: local\ntools:{tool_yaml}\n---\n\n{body}")
        elif target == "agents":
            writer.write(f"{lay['skills']}/agent-{a.name}/SKILL.md",
                         f"---\nname: agent-{a.name}\ndescription: {yaml_str(('Rol de agente ' + a.name + '. ' + desc)[:1024])}\n---\n\n"
                         f"# Rol: {a.name}\n\nAdopta este rol y sigue sus instrucciones."
                         f"{' Es un rol de solo lectura: no modifiques archivos.' if a.readonly else ''}\n\n{body}")

    # Comandos
    for c in data["commands"]:
        desc = flatten(c.meta.get("description", c.name))
        hint = c.meta.get("argument-hint", "")
        body = to_text(args_placeholder(c.body, target))
        arg_note = (f"> `<argumentos>` = el texto que el usuario escribió junto al comando"
                    f"{f' (formato: `{hint}`)' if hint else ''}. Si está vacío, trátalo como vacío.\n\n")
        if target in ("codex", "agents"):
            name = c.name if target == "codex" else f"cmd-{c.name}"
            invocation = f"${name}" if target == "codex" else name
            writer.write(f"{lay['skills']}/{name}/SKILL.md",
                         f"---\nname: {name}\ndescription: {yaml_str(f'Comando {invocation}: {desc}. Usar solo cuando el usuario lo invoque explícitamente.')}\n---\n\n"
                         f"# Comando {invocation}\n\n{arg_note}{body}")
            if target == "codex":
                writer.write(f"{lay['skills']}/{name}/agents/openai.yaml",
                             f"interface:\n  display_name: {yaml_str(c.name)}\n  short_description: {yaml_str(desc[:120])}\n"
                             "policy:\n  allow_implicit_invocation: false\n")
        elif target == "cursor" and lay.get("commands"):
            writer.write(f"{lay['commands']}/{c.name}.md", f"# {desc}\n\n{arg_note}{body}")
        elif target == "copilot" and lay.get("commands"):
            writer.write(f"{lay['commands']}/{c.name}.prompt.md",
                         f"---\ndescription: {yaml_str(desc)}\nagent: agent\n"
                         f"{f'argument-hint: {yaml_str(hint)}' + chr(10) if hint else ''}---\n\n{arg_note}{body}")
        elif target == "gemini" and lay.get("commands"):
            writer.write(f"{lay['commands']}/{c.name}.toml",
                         f"description = {toml_str(desc)}\nprompt = {toml_multiline(body)}\n")

    # Contexto general
    if lay.get("context"):
        writer.context_block(lay["context"], context_markdown(data, user))


# ---------------------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, help=f"{', '.join(TARGETS)} o all (separados por coma)")
    ap.add_argument("--dest", default=".", help="Proyecto destino (por defecto: directorio actual)")
    ap.add_argument("--user", action="store_true", help="Instalar a nivel usuario (en el home) en vez de en un proyecto")
    ap.add_argument("--plugins", default=",".join(PLUGIN_ORDER), help="Plugins a exportar (por defecto: todos)")
    ap.add_argument("--dry-run", action="store_true", help="Mostrar qué se generaría sin escribir nada")
    ap.add_argument("--force", action="store_true", help="Sobrescribir archivos existentes no generados por este script")
    ap.add_argument("--skip-skills", action="store_true",
                    help="No copiar skills (ya las da el plugin nativo, p. ej. en Codex); exporta agentes, comandos y contexto")
    ap.add_argument("--uninstall", action="store_true", help="Eliminar todo lo generado previamente para el target")
    args = ap.parse_args()

    targets = TARGETS if args.target == "all" else [t.strip() for t in args.target.split(",")]
    for t in targets:
        if t not in TARGETS:
            sys.exit(f"Target desconocido: {t}. Opciones: {', '.join(TARGETS)}, all")
    plugins = [p.strip() for p in args.plugins.split(",") if p.strip()]
    if "core" not in plugins:
        print("Aviso: sin 'core' los agentes pierden la información general (project-context).", file=sys.stderr)
    dest = Path.home() if args.user else Path(args.dest).expanduser().resolve()
    data = load(plugins)

    for target in targets:
        writer = Writer(dest, target, args.dry_run, args.force)
        if args.uninstall:
            for rel in sorted(writer.previous - writer.others):
                if not args.dry_run:
                    remove(dest, rel)
            if not args.dry_run and writer.manifest_path.exists():
                writer.manifest_path.unlink()
            state_dir = writer.manifest_path.parent
            if not args.dry_run and state_dir.is_dir() and not any(state_dir.iterdir()):
                state_dir.rmdir()
            print(f"[{target}] desinstalado: {len(writer.previous)} entradas{' (dry-run)' if args.dry_run else ''}")
            continue
        export(target, data, writer, args.user, args.skip_skills)
        stale = writer.finish()
        print(f"[{target}] {len(writer.files)} archivos en {dest}{' (dry-run)' if args.dry_run else ''}"
              f"{f' · {len(stale)} obsoletos eliminados' if stale else ''}")
        for rel in writer.skipped:
            print(f"  omitido (ya existe y no es de My Agents; usa --force): {rel}")
        if args.user and target in ("cursor", "copilot", "agents"):
            print(f"  nota: {target} no tiene archivo de contexto global; ejecuta también con --dest en cada proyecto.")


if __name__ == "__main__":
    main()
