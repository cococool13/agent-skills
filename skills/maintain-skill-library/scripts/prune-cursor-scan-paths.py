#!/usr/bin/env python3
"""Keep one live copy of each skill on Cursor's scan paths.

Cursor indexes ~/.agents/skills, ~/.cursor/skills, and ~/.codex/skills.
Do not recreate ~/.claude. Extra copies make every slash entry appear
twice. Canonical store is ~/.agents/skills.

Does not touch ~/.cursor/skills-cursor or plugin caches.
Retirements go to ~/.agents/skill-archive/<stamp>/ (never rm).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
from pathlib import Path

HOME = Path.home()
AGENTS = HOME / ".agents" / "skills"
CLAUDE = HOME / ".claude" / "skills"
CODEX = HOME / ".codex" / "skills"
CURSOR = HOME / ".cursor" / "skills"
COMMANDS = HOME / ".claude" / "commands"
LOCK = HOME / ".agents" / ".skill-lock.json"

KEEP_IN_VIEWS = {
    "changelog.md",
    "README.md",
    "_archive",
    ".DS_Store",
    ".impeccable",
}

# Cursor built-in /review already exists. Park leftover command files if
# a ~/.claude/commands dir ever reappears.
PARK_COMMANDS = ("ship.md", "review.md")


def stamp() -> str:
    return dt.date.today().isoformat()


def archive_root() -> Path:
    root = HOME / ".agents" / "skill-archive" / f"{stamp()}-cursor-dedupe"
    root.mkdir(parents=True, exist_ok=True)
    return root


def agent_names() -> set[str]:
    names: set[str] = set()
    if not AGENTS.is_dir():
        return names
    for p in AGENTS.iterdir():
        if p.name.startswith(".") or p.name in KEEP_IN_VIEWS:
            continue
        if p.is_dir() or p.is_symlink():
            names.add(p.name)
    return names


def retire(path: Path, dest_dir: Path, log: list[str]) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if dest.exists() or dest.is_symlink():
        dest = dest_dir / f"{path.name}.{os.getpid()}"
    shutil.move(str(path), str(dest))
    log.append(f"parked {path} -> {dest}")


def prune_view(view: Path, names: set[str], dest_dir: Path, log: list[str]) -> None:
    if not view.is_dir():
        return
    for p in list(view.iterdir()):
        if p.name.startswith(".") and p.name not in {".impeccable"}:
            continue
        if p.name in KEEP_IN_VIEWS:
            continue
        if p.name in names or p.is_symlink():
            retire(p, dest_dir, log)


def prune_commands(dest_dir: Path, log: list[str]) -> None:
    if not COMMANDS.is_dir():
        return
    for name in PARK_COMMANDS:
        p = COMMANDS / name
        if p.exists() or p.is_symlink():
            retire(p, dest_dir, log)


def resolves_into_agents(path: Path) -> bool:
    """True when a symlink resolves under the canonical agents library."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    try:
        resolved.relative_to(AGENTS.resolve())
        return True
    except ValueError:
        return False


def prune_broken_cursor_links(dest_dir: Path, log: list[str]) -> None:
    """Retire broken links and real duplicate dirs in ~/.cursor/skills.

    Keep symlinks that resolve into ~/.agents/skills — those are the
    Sync Skills / cloud sync source (one live copy, not a second library).
    """
    if not CURSOR.is_dir():
        return
    names = agent_names()
    for p in list(CURSOR.iterdir()):
        if p.name in KEEP_IN_VIEWS or p.name == "README.md":
            continue
        if p.is_symlink():
            if not p.resolve().exists():
                retire(p, dest_dir, log)
            elif not resolves_into_agents(p):
                retire(p, dest_dir, log)
            continue
        if p.name in names and p.is_dir():
            retire(p, dest_dir, log)


def pin_lockfile(log: list[str]) -> None:
    if not LOCK.is_file():
        return
    data = json.loads(LOCK.read_text())
    wanted = ["cursor"]
    if data.get("lastSelectedAgents") != wanted:
        data["lastSelectedAgents"] = wanted
        LOCK.write_text(json.dumps(data, indent=2) + "\n")
        log.append("pinned .skill-lock.json lastSelectedAgents to [cursor]")


def write_view_readmes() -> None:
    cursor_readme = """# Cursor user skills

Canonical library: `~/.agents/skills`.

For Cursor Cloud / Sync Skills, keep **symlinks** here that point into
`~/.agents/skills` (not real copies). Weekly prune keeps those links and
only retires broken links or duplicate real directories.

Also loaded:

- `~/.agents/skills` — personal and source-managed skills (canonical)
- `~/.cursor/skills-cursor` — Cursor built-ins (managed by Cursor)

Keep `~/.codex/skills` empty of skills. Do not recreate `~/.claude`.

Check **Customize → Skills** after a window reload to see the live set.
"""
    (CURSOR / "README.md").write_text(cursor_readme)
    if CODEX.parent.is_dir():
        CODEX.mkdir(parents=True, exist_ok=True)
        (CODEX / "README.md").write_text(
            """# Codex skill view

Do not put shared skills here. Cursor scans this folder.

Canonical store: `~/.agents/skills` (Cursor, Grok, and the skills CLI).
"""
        )


def main() -> int:
    names = agent_names()
    dest = archive_root()
    log: list[str] = []
    prune_view(CLAUDE, names, dest / "claude-skills", log)
    prune_view(CODEX, names, dest / "codex-skills", log)
    prune_commands(dest / "claude-commands", log)
    prune_broken_cursor_links(dest / "cursor-skills", log)
    pin_lockfile(log)
    write_view_readmes()
    summary = dest / "MANIFEST.txt"
    summary.write_text("\n".join(log) + ("\n" if log else "(nothing to park)\n"))
    print(f"canonical {AGENTS} ({len(names)} skills)")
    print(f"archive {dest}")
    print(f"parked {len(log)} items")
    for line in log:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
