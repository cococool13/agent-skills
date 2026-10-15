#!/usr/bin/env python3
"""Keep every agent's view of ~/.agents/skills correct. Symlinks only; no copies.

- ~/.claude/skills and ~/.cursor/skills: one link per canonical skill, plus the
  Grok ponytail plugin skills (found by glob, so plugin hash changes self-heal).
- Host built-in copies are reported for review. Scheduled sync never archives
  a real directory or republishes host-specific copies into another client.
- ~/.local/share/node-current points at the nvm default Node, so MCP configs
  never pin a version.

Real directories and claude.ai downloads (skills/synced) are left alone.
"""
from __future__ import annotations

import os
from pathlib import Path

HOME = Path.home()
CANON = HOME / ".agents/skills"
HOST_BUILTINS = HOME / ".cursor/skills-cursor"
PONYTAIL = HOME / ".grok/installed-plugins"
# Unused plugin extras (2026-10-14 audit); Grok keeps them.
PONYTAIL_SKIP = {"ponytail-audit", "ponytail-debt", "ponytail-gain", "ponytail-help"}
VIEWS = {"claude": HOME / ".claude/skills", "cursor": HOME / ".cursor/skills"}
NVM = HOME / ".nvm"
NODE_LINK = HOME / ".local/share/node-current"


def is_host_copy(path: Path) -> bool:
    builtin = HOST_BUILTINS / path.name / "SKILL.md"
    skill = path / "SKILL.md"
    if not builtin.is_file() or not skill.is_file():
        return False
    original = builtin.read_text()
    return skill.read_text() in {original, original.replace("Cursor", "Codex")}


def host_copies() -> list[str]:
    if not HOST_BUILTINS.is_dir():
        return []
    found = []
    for builtin in sorted(HOST_BUILTINS.iterdir()):
        copy = CANON / builtin.name
        if copy.is_dir() and not copy.is_symlink() and is_host_copy(copy):
            found.append(builtin.name)
    return found


def wanted() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(CANON.iterdir()) if CANON.is_dir() else []:
        if is_host_copy(path):
            continue
        if not path.name.startswith(".") and (path / "SKILL.md").is_file():
            found[path.name] = path
    for skill_root in sorted(PONYTAIL.glob("ponytail-*/skills")):
        for path in sorted(skill_root.iterdir()):
            if path.name in PONYTAIL_SKIP:
                continue
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
        (p for p in versions.iterdir()
         if p.is_dir() and (p.name.lstrip("v") == wanted_version
                            or p.name.lstrip("v").startswith(wanted_version + "."))),
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
    copies = host_copies()
    if copies:
        print(f"host-specific copies retained for review: {', '.join(copies)}")
    targets = wanted()
    for host, dest in VIEWS.items():
        print(f"{host} skills: {sync_view(dest, targets)}")
    print(sync_node_link())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
