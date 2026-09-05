#!/usr/bin/env python3
"""Remove stale owned git worktrees in the current repo. Unique or dirty trees stay. Trash, never rm."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib import (  # noqa: E402
    OWNED_WT,
    cherry_unique,
    current_repo,
    git,
    git_ok,
    git_run,
    owned_rel,
    parse_worktrees,
)


def unique_vs_primary(primary: Path, tree: Path) -> bool:
    head = git(tree, "rev-parse", "HEAD")
    if not head:
        return False
    base = git(primary, "rev-parse", "HEAD") or "HEAD"
    if git_ok(primary, "merge-base", "--is-ancestor", head, base):
        return False
    return bool(cherry_unique(primary, head, base))


def is_dirty(tree: Path) -> bool:
    return bool(git(tree, "status", "--porcelain"))


def trash_dir(src: Path, dest_root: Path) -> str:
    dest = dest_root / src.name
    n = 1
    while dest.exists():
        dest = dest_root / f"{src.name}-{n}"
        n += 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dest)
    return str(dest)


def leftover_dirs(repo: Path) -> list[Path]:
    out: list[Path] = []
    for d in OWNED_WT:
        parent = repo / d
        if parent.is_dir():
            out.extend(p for p in parent.iterdir() if p.is_dir())
    return out


def empty_cleanup() -> dict:
    return {"trash": "", "repos": 0, "removed": 0, "kept": 0, "reports": []}


def process_repo(repo: Path, trash: Path) -> dict:
    result = {"repo": str(repo), "removed": [], "trashed": [], "kept": [], "pruned": False}
    trees = parse_worktrees(repo)

    seen: set[Path] = set()
    kept_paths: set[Path] = set()
    for t in trees:
        path: Path = t["path"]
        seen.add(path.resolve())
        if path.resolve() == repo.resolve():
            continue
        if not owned_rel(repo, path):
            result["kept"].append({"path": str(path), "reason": "not-owned"})
            kept_paths.add(path.resolve())
            continue
        if path.exists() and is_dirty(path):
            result["kept"].append({"path": str(path), "reason": "dirty"})
            kept_paths.add(path.resolve())
            continue
        if path.exists() and unique_vs_primary(repo, path):
            result["kept"].append({"path": str(path), "reason": "unique-commits"})
            kept_paths.add(path.resolve())
            continue
        rm = git_run(repo, "worktree", "remove", str(path))
        if rm.returncode != 0:
            git_run(repo, "worktree", "prune")
        if path.exists():
            result["trashed"].append(trash_dir(path, trash / repo.name))
        else:
            result["removed"].append(str(path))

    for leftover in leftover_dirs(repo):
        resolved = leftover.resolve()
        if resolved in seen or resolved in kept_paths:
            continue
        gitdir = leftover / ".git"
        if gitdir.exists():
            if is_dirty(leftover):
                result["kept"].append({"path": str(leftover), "reason": "dirty"})
                continue
            if unique_vs_primary(repo, leftover):
                result["kept"].append({"path": str(leftover), "reason": "unique-commits"})
                continue
        result["trashed"].append(trash_dir(leftover, trash / repo.name))

    prune = git_run(repo, "worktree", "prune", "-v")
    result["pruned"] = prune.returncode == 0
    if prune.stdout and prune.stdout.strip():
        result["prune_log"] = prune.stdout.strip()

    for d in OWNED_WT:
        parent = repo / d
        if parent.is_dir() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError:
                pass
    return result


def cleanup_repo(repo: Path, trash: Path | None = None) -> dict:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    owned_trash = trash is None
    if trash is None:
        trash = Path.home() / ".Trash" / f"ship-worktrees-{stamp}"
    trash.mkdir(parents=True, exist_ok=True)
    reports = [process_repo(repo, trash)]
    removed = sum(len(r["removed"]) + len(r["trashed"]) for r in reports)
    kept = sum(len(r["kept"]) for r in reports)
    trash_s = str(trash)
    if removed == 0 and owned_trash:
        try:
            trash.rmdir()
            trash_s = ""
        except OSError:
            pass
    return {
        "trash": trash_s,
        "repos": len(reports),
        "removed": removed,
        "kept": kept,
        "reports": reports,
    }


def format_cleanup(result: dict) -> str:
    lines = [f"worktrees: removed {result['removed']}, kept {result['kept']}"]
    if result["trash"]:
        lines.append(f"trash: {result['trash']}")
    for r in result["reports"]:
        if not (r["removed"] or r["trashed"] or r["kept"] or r.get("prune_log")):
            continue
        lines.append(r["repo"])
        for p in r["removed"]:
            lines.append(f"  removed {p}")
        for p in r["trashed"]:
            lines.append(f"  trashed {p}")
        for k in r["kept"]:
            lines.append(f"  kept {k['path']} ({k['reason']})")
        if r.get("prune_log"):
            lines.append(f"  prune {r['prune_log']}")
    return "\n".join(lines)


def main() -> int:
    repo = current_repo()
    if repo is None:
        print("not a git repo — nothing to clean", file=sys.stderr)
        return 1
    print(format_cleanup(cleanup_repo(repo)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
