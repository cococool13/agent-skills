#!/usr/bin/env python3
"""Sync newer agent docs from owned worktrees into the main checkout."""

from __future__ import annotations

import shutil
from pathlib import Path

from lib import AGENT_DOCS, git, owned_rel
from worktrees import leftover_dirs


def owned_worktree_paths(repo: Path) -> list[Path]:
    paths: list[Path] = []
    porcelain = git(repo, "worktree", "list", "--porcelain")
    cur: dict = {}
    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            if cur:
                paths.append(Path(cur["path"]))
            cur = {"path": line[9:]}
    if cur:
        paths.append(Path(cur["path"]))

    out: list[Path] = []
    seen: set[Path] = set()
    for p in paths + leftover_dirs(repo):
        resolved = p.resolve()
        if resolved in seen or resolved == repo.resolve():
            continue
        seen.add(resolved)
        if p.is_dir() and owned_rel(repo, p):
            out.append(p)
    return out


def sync_agent_docs(repo: Path) -> list[dict]:
    """Copy the newest agent doc from main + owned worktrees into repo root."""
    synced: list[dict] = []
    best: dict[str, tuple[Path, float]] = {}

    for name in AGENT_DOCS:
        main = repo / name
        if main.is_file():
            best[name] = (main, main.stat().st_mtime)

    for wt in owned_worktree_paths(repo):
        for name in AGENT_DOCS:
            src = wt / name
            if not src.is_file():
                continue
            mtime = src.stat().st_mtime
            cur = best.get(name)
            if cur is None or mtime > cur[1]:
                best[name] = (src, mtime)

    for name, (src, _) in best.items():
        dest = repo / name
        if src.resolve() == dest.resolve():
            continue
        try:
            if dest.is_file() and dest.read_bytes() == src.read_bytes():
                continue
        except OSError:
            pass
        shutil.copy2(src, dest)
        synced.append({"path": name, "from": str(src.parent)})
    return synced
