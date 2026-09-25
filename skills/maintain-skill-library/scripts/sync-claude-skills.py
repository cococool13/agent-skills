#!/usr/bin/env python3
"""Keep every agent's view of ~/.agents/skills correct. Symlinks only; no copies.

- ~/.claude/skills and ~/.cursor/skills: one link per canonical skill, plus the
  Grok ponytail plugin skills (found by glob, so plugin hash changes self-heal).
- Host built-in copies (names that ship in ~/.cursor/skills-cursor) are moved
  out of the canonical library into ~/.agents/_archive, so no host loads a
  skill written for a different host.
- ~/.local/share/node-current points at the nvm default Node, so MCP configs
  never pin a version.

Real directories and claude.ai downloads (skills/synced) are left alone.
"""
from __future__ import annotations

import datetime
import os
import shutil
from pathlib import Path

HOME = Path.home()
CANON = HOME / ".agents/skills"
ARCHIVE = HOME / ".agents/_archive"
HOST_BUILTINS = HOME / ".cursor/skills-cursor"
PONYTAIL = HOME / ".grok/installed-plugins"
VIEWS = {"claude": HOME / ".claude/skills", "cursor": HOME / ".cursor/skills"}
NVM = HOME / ".nvm"
NODE_LINK = HOME / ".local/share/node-current"


def archive_host_copies() -> list[str]:
    if not HOST_BUILTINS.is_dir():
        return []
    moved = []
    dest = ARCHIVE / f"{datetime.date.today()}-host-skill-copies"
    for builtin in HOST_BUILTINS.iterdir():
        copy = CANON / builtin.name
        if copy.is_dir() and not copy.is_symlink():
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / builtin.name
            if target.exists():
                target = dest / f"{builtin.name}-{datetime.datetime.now():%H%M%S}"
            shutil.move(str(copy), target)
            moved.append(builtin.name)
    return moved


def wanted() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(CANON.iterdir()) if CANON.is_dir() else []:
        if not path.name.startswith(".") and (path / "SKILL.md").is_file():
            found[path.name] = path
    for skill_root in sorted(PONYTAIL.glob("ponytail-*/skills")):
        for path in sorted(skill_root.iterdir()):
            if path.name not in found and (path / "SKILL.md").is_file():
                found[path.name] = path
    return found


def sync_view(dest: Path, targets: dict[str, Path]) -> str:
    dest.mkdir(parents=True, exist_ok=True)
    counts = {"linked": 0, "kept": 0, "skipped-real": 0, "removed": 0}
    for name, target in targets.items():
        link = dest / name
        if link.is_symlink():
            if Path(os.readlink(link)) == target or link.resolve() == target.resolve():
                counts["kept"] += 1
                continue
            link.unlink()
        elif link.exists():
            counts["skipped-real"] += 1
            continue
        link.symlink_to(target)
        counts["linked"] += 1
    for link in sorted(dest.iterdir()):
        if link.name in targets or link.name == "synced" or not link.is_symlink():
            continue
        raw = os.readlink(link)
        if ".agents/skills" in raw or "ponytail-" in raw or not link.exists():
            link.unlink()
            counts["removed"] += 1
    return ", ".join(f"{v} {k}" for k, v in counts.items())


def sync_node_link() -> str:
    alias = NVM / "alias/default"
    versions = NVM / "versions/node"
    if not versions.is_dir():
        return "node-current: no nvm"
    wanted_version = alias.read_text().strip().lstrip("v") if alias.is_file() else ""
    matches = sorted(
        (p for p in versions.iterdir() if p.name.lstrip("v").startswith(wanted_version)),
        key=lambda p: [int(x) if x.isdigit() else 0 for x in p.name.lstrip("v").split(".")],
    )
    if not matches:
        return f"node-current: no install matches alias {wanted_version!r}"
    target = matches[-1]
    if NODE_LINK.is_symlink() and NODE_LINK.resolve() == target.resolve():
        return f"node-current: {target.name}"
    NODE_LINK.parent.mkdir(parents=True, exist_ok=True)
    if NODE_LINK.is_symlink():
        NODE_LINK.unlink()
    NODE_LINK.symlink_to(target)
    return f"node-current: now {target.name}"


def main() -> int:
    moved = archive_host_copies()
    if moved:
        print(f"archived host built-in copies: {', '.join(moved)}")
    targets = wanted()
    for host, dest in VIEWS.items():
        print(f"{host} skills: {sync_view(dest, targets)}")
    print(sync_node_link())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
