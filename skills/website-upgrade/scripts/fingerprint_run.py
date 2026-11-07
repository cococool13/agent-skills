#!/usr/bin/env python3
"""Fingerprint a target checkout so resume can detect stale evidence.

Records commit, branch, a dirty-tree digest, and a config digest.
Does not print file contents. Secret-looking paths contribute path,
size, and mtime only — not a content hash. Symlinks are followed only
when the target stays inside the checkout; external targets are not
opened or content-hashed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SECRET_SUFFIXES = (
    ".env",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".mobileprovision",
)
SECRET_NAMES = {
    ".env",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.json",
    "auth.json",
}
CONFIG_CANDIDATES = (
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "pyproject.toml",
    "poetry.lock",
    "requirements.txt",
    "Package.swift",
    "Package.resolved",
    "Podfile",
    "Podfile.lock",
    "Gemfile.lock",
    "composer.lock",
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
)


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def looks_secret(path: Path) -> bool:
    name = path.name.lower()
    if name in SECRET_NAMES or name.startswith(".env"):
        return True
    return path.suffix.lower() in SECRET_SUFFIXES


def _resolves_inside(repo: Path, path: Path) -> bool:
    """True when path resolves inside repo. Does not read file contents."""
    try:
        path.resolve().relative_to(repo.resolve())
    except (OSError, ValueError):
        return False
    return True


def digest_file(repo: Path, path: Path) -> str:
    # Follow a symlink only when its target stays inside the checkout.
    # An external target is not opened or content-hashed; the link path is marked.
    try:
        if path.is_symlink() and not _resolves_inside(repo, path):
            return hashlib.sha256(f"outside-symlink:{path.as_posix()}".encode()).hexdigest()
    except OSError:
        return hashlib.sha256(f"unreadable:{path.as_posix()}".encode()).hexdigest()
    if looks_secret(path):
        try:
            st = path.stat()
            payload = f"secret:{path.as_posix()}:{st.st_size}:{int(st.st_mtime)}"
        except OSError:
            payload = f"secret-missing:{path.as_posix()}"
        return hashlib.sha256(payload.encode()).hexdigest()
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 64), b""):
                h.update(chunk)
    except OSError:
        return hashlib.sha256(f"unreadable:{path.as_posix()}".encode()).hexdigest()
    return h.hexdigest()


def dirty_digest(repo: Path) -> tuple[str, list[str], bool]:
    if not (repo / ".git").exists() and run_git(repo, "rev-parse", "--is-inside-work-tree").returncode != 0:
        # Not a git work tree: hash a shallow listing so resume still notices churn.
        names = sorted(
            p.relative_to(repo).as_posix()
            for p in repo.rglob("*")
            if p.is_file() and ".git" not in p.parts
        )[:400]
        h = hashlib.sha256()
        listed: list[str] = []
        for rel in names:
            listed.append(rel)
            h.update(rel.encode())
            h.update(b"\0")
            h.update(digest_file(repo, repo / rel).encode())
        return h.hexdigest(), listed, False

    porcelain = run_git(repo, "status", "--porcelain", "-uall")
    lines = [ln for ln in porcelain.stdout.splitlines() if ln.strip()]
    h = hashlib.sha256()
    h.update(porcelain.stdout.encode())
    names: list[str] = []
    for line in lines:
        rel = line[3:].strip()
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        names.append(rel)
        path = repo / rel
        if path.is_file():
            h.update(b"\n")
            h.update(rel.encode())
            h.update(b"\0")
            h.update(digest_file(repo, path).encode())
    return h.hexdigest(), names, True


def config_hash(repo: Path) -> str:
    h = hashlib.sha256()
    found = 0
    for name in CONFIG_CANDIDATES:
        path = repo / name
        if path.is_file():
            found += 1
            h.update(name.encode())
            h.update(b"\0")
            h.update(digest_file(repo, path).encode())
            h.update(b"\n")
    if found == 0:
        return "none"
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path, help="target repository or project directory")
    parser.add_argument("--out", type=Path, help="write JSON here; default stdout")
    parser.add_argument("--scoped-path", default=".", help="area or path from $ARGUMENTS")
    parser.add_argument("--mode", default="report-only")
    parser.add_argument("--depth", default="standard")
    parser.add_argument(
        "--unknown-flags",
        default="",
        help="space-separated unknown flags to record",
    )
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"ERROR: not a directory: {repo}", file=sys.stderr)
        return 2

    git_ok = run_git(repo, "rev-parse", "--is-inside-work-tree")
    inside = git_ok.returncode == 0 and git_ok.stdout.strip() == "true"
    commit = None
    branch = None
    if inside:
        commit_p = run_git(repo, "rev-parse", "HEAD")
        branch_p = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        if commit_p.returncode == 0:
            commit = commit_p.stdout.strip()
        if branch_p.returncode == 0:
            branch = branch_p.stdout.strip()

    dirty, dirty_names, git_present = dirty_digest(repo)
    meta = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": str(repo),
        "scopedPath": args.scoped_path,
        "mode": args.mode,
        "depth": args.depth,
        "unknownFlags": [f for f in args.unknown_flags.split() if f],
        "gitWorkTree": inside and git_present,
        "commit": commit,
        "branch": branch,
        "dirtyDigest": dirty,
        "dirtyPaths": dirty_names,
        "configHash": config_hash(repo),
        "tool": "scripts/fingerprint_run.py",
    }

    payload = json.dumps(meta, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
