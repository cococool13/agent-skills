#!/usr/bin/env python3
"""Report and pin upstream refs for third-party skills in ~/.agents/.skill-lock.json.

  skill-refs.py report [--out FILE]   Markdown diff report: locked folder hash vs upstream HEAD.
  skill-refs.py pin [--dry-run]       Add `ref` (a commit sha) to third-party entries without one.
                                      The sha is the newest commit whose skill folder matches the
                                      installed `skillFolderHash`; HEAD when no match is found.

Read-only GitHub calls go through `gh api`. Original personal skills (cococool13/*) are skipped.
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

LOCK = Path.home() / ".agents/.skill-lock.json"
PERSONAL = ("cococool13/",)


def gh(path: str):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)


def folder_of(skill_path: str) -> str:
    folder = skill_path.replace("\\", "/")
    for suffix in ("/SKILL.md", "SKILL.md"):
        if folder.lower().endswith(suffix.lower()):
            folder = folder[: -len(suffix)]
            break
    return folder.rstrip("/")


def folder_hash(source: str, ref: str, folder: str, cache: dict):
    key = (source, ref)
    if key not in cache:
        cache[key] = gh(f"repos/{source}/git/trees/{ref}?recursive=1")
    tree = cache[key]
    if not tree:
        return None
    if not folder:
        return tree.get("sha")
    for entry in tree.get("tree", []):
        if entry.get("type") == "tree" and entry.get("path") == folder:
            return entry.get("sha")
    return None


def head_sha(source: str, cache: dict):
    if source not in cache:
        data = gh(f"repos/{source}/commits/HEAD")
        cache[source] = data.get("sha") if data else None
    return cache[source]


def matching_commit(source: str, folder: str, want: str, trees: dict):
    commits = gh(f"repos/{source}/commits?path={folder}&per_page=15") if folder else None
    for commit in commits or []:
        sha = commit.get("sha")
        if sha and folder_hash(source, sha, folder, trees) == want:
            return sha
    return None


def third_party(entry: dict) -> bool:
    return entry.get("sourceType") == "github" and not str(entry.get("source", "")).startswith(PERSONAL)


def report(out: Path | None) -> int:
    lock = json.loads(LOCK.read_text())
    heads, trees = {}, {}
    rows, moved = [], 0
    for name, entry in sorted(lock["skills"].items()):
        source, folder = entry.get("source", ""), folder_of(entry.get("skillPath", ""))
        head = head_sha(source, heads) if entry.get("sourceType") == "github" else None
        upstream = folder_hash(source, head, folder, trees) if head else None
        locked = entry.get("skillFolderHash")
        ref = entry.get("ref")
        if not third_party(entry):
            status = "personal"
        elif upstream is None:
            status = "upstream unreachable"
        elif upstream == locked:
            status = "current"
        else:
            status = "upstream moved"
            moved += 1
        rows.append(f"| {name} | {source} | {(ref or '-')[:12]} | {(locked or '-')[:10]} | {(upstream or '-')[:10]} | {status} |")
    text = "\n".join([
        f"# Skills update report {datetime.date.today().isoformat()}",
        "",
        f"{len(rows)} lock entries; {moved} third-party skills changed upstream since install.",
        "Pinned entries (`ref` = sha) do not change on `skills update`. To take an upstream change: review the diff,",
        "set the entry's `ref` to the new sha with `skill-refs.py`, then run the update script.",
        "",
        "| Skill | Source | Ref | Locked | Upstream HEAD | Status |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ])
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        print(f"report: {out} ({moved} moved upstream)")
    else:
        print(text)
    return 0


def pin(dry_run: bool) -> int:
    lock = json.loads(LOCK.read_text())
    heads, trees = {}, {}
    pinned, exact, failed = 0, 0, []
    for name, entry in sorted(lock["skills"].items()):
        if not third_party(entry) or entry.get("ref"):
            continue
        source, folder = entry["source"], folder_of(entry.get("skillPath", ""))
        head = head_sha(source, heads)
        if not head:
            failed.append(name)
            continue
        want = entry.get("skillFolderHash")
        sha = head if folder_hash(source, head, folder, trees) == want else matching_commit(source, folder, want, trees)
        if sha:
            exact += 1
        entry["ref"] = sha or head
        pinned += 1
    print(f"pinned {pinned} entries ({exact} to the commit matching the installed files, "
          f"{pinned - exact} to HEAD); unreachable: {', '.join(failed) or 'none'}")
    if not dry_run and pinned:
        backup = LOCK.with_name(LOCK.name + ".bak-fix-2026-10-19")
        if not backup.exists():
            shutil.copy2(LOCK, backup)
        LOCK.write_text(json.dumps(lock, indent=2) + "\n")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--out", type=Path)
    p = sub.add_parser("pin")
    p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return report(args.out) if args.cmd == "report" else pin(args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
