#!/usr/bin/env python3
"""Shared git helpers for /ship."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

OWNED_WT = (".claude/worktrees", ".worktrees", "worktrees")
SECRET_RE = re.compile(
    r"(password|passwords|secret|credential|bitwarden|1password|lastpass|"
    r"keepass|applepasswords|recovery.?code|backup.?code|seed.?phrase|"
    r"mnemonic|id_rsa|id_ed25519|service-account|credentials\.json|"
    r"\.pem$|\.key$|\.p12$|keychain|(?:^|/)\.env(?:$|\.))",
    re.I,
)
NOISE_RE = re.compile(
    r"(?:^|/)\.DS_Store$|(?:^|/)Thumbs\.db$|\.pyc$|(?:^|/)__pycache__(?:/|$)|"
    r"(?:^|/)\.uizze/live/|\.log$|\.tsbuildinfo$|\.orig$|\.rej$|"
    r"(?:^|/)\.claude/worktrees/|(?:^|/)\.worktrees/|(?:^|/)\.turbo/|(?:^|/)coverage/",
    re.I,
)
SECRET_CONTENT = re.compile(
    r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}"
)
AGENT_DOCS = {"AGENTS.md", "CLAUDE.md", "CONTEXT.md"}
REMOTE_SKIP = re.compile(r"/(HEAD|main|master)$")
MAX_UNTRACKED = 5 * 1024 * 1024


_identity: tuple[str, str] | None | bool = False


def github_noreply_identity() -> tuple[str, str] | None:
    """Commit as GitHub noreply so GH007 cannot block the push. Does not write git config."""
    global _identity
    if _identity is not False:
        return _identity if isinstance(_identity, tuple) else None
    try:
        r = subprocess.run(["gh", "api", "user"], capture_output=True, text=True, timeout=20)
        u = json.loads(r.stdout) if r.returncode == 0 and r.stdout else {}
        login = str(u.get("login") or "")
        uid = u.get("id")
        name = str(u.get("name") or login).strip()
        if r.returncode != 0 or not login or uid is None:
            _identity = None
            return None
        _identity = (name, f"{uid}+{login}@users.noreply.github.com")
        return _identity
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, TypeError):
        _identity = None
        return None


def git_run(
    repo: Path,
    *args: str,
    timeout: int | None = 120,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(repo)]
    ident = github_noreply_identity()
    if ident:
        cmd.extend(["-c", f"user.name={ident[0]}", "-c", f"user.email={ident[1]}"])
    cmd.extend(args)
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, env=env)


def git(repo: Path, *args: str, timeout: int | None = 120) -> str:
    return (git_run(repo, *args, timeout=timeout).stdout or "").rstrip()


def git_ok(repo: Path, *args: str, timeout: int | None = 120) -> bool:
    return git_run(repo, *args, timeout=timeout).returncode == 0


def current_repo() -> Path | None:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    if r.returncode != 0:
        return None
    return Path(r.stdout.strip())


def default_base(repo: Path) -> str:
    for name in ("main", "master"):
        if git_ok(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{name}"):
            return name
    return "HEAD"


def parse_worktrees(repo: Path) -> list[dict]:
    trees: list[dict] = []
    cur: dict = {}
    for line in git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            if cur:
                trees.append(cur)
            cur = {"path": Path(line[9:])}
        elif line.startswith("branch "):
            cur["branch"] = line[7:]
        elif line.startswith("prunable"):
            cur["prunable"] = True
    if cur:
        trees.append(cur)
    return trees


def parse_status(repo: Path) -> list[dict]:
    rows = []
    for line in git(repo, "status", "--porcelain", "-uall").splitlines():
        if len(line) < 4:
            continue
        xy, rest = line[:2], line[3:]
        path = rest.split(" -> ", 1)[1] if " -> " in rest else rest
        rows.append({"path": path, "xy": xy, "untracked": xy == "??"})
    return rows


def bucket_file(path: str, untracked: bool, repo: Path | None = None) -> str:
    if SECRET_RE.search(path):
        return "secret"
    if NOISE_RE.search(path):
        return "noise"
    if untracked and ("/_archive/" in f"/{path}" or path.startswith("_archive/")):
        return "archive"
    if untracked and repo is not None:
        p = repo / path
        try:
            if p.is_file() and p.stat().st_size > MAX_UNTRACKED:
                return "noise"
        except OSError:
            pass
    return "commit"


def looks_secret(text: str) -> bool:
    return bool(SECRET_CONTENT.search(text or ""))


def suggest_msg(files: list[str]) -> str:
    if not files:
        return "chore: ship pending work"
    names = {Path(f).name for f in files}
    if names <= AGENT_DOCS:
        return "docs: refresh agent files"
    if all(Path(f).suffix == ".md" for f in files):
        return "docs: update project notes"
    if len(files) == 1:
        name = Path(files[0]).name
        kind = "docs" if name.endswith(".md") else "chore"
        msg = f"{kind}: update {name}"
        return msg[:72]
    md = sum(1 for f in files if f.endswith(".md"))
    if md * 2 >= len(files):
        return "docs: update project files"
    return f"chore: ship {len(files)} pending files"


def is_ancestor(repo: Path, maybe_old: str, maybe_new: str) -> bool:
    return git_ok(repo, "merge-base", "--is-ancestor", maybe_old, maybe_new)


def merge_preview(repo: Path, base: str, ref: str) -> dict:
    """Would merging ref into base be clean, and would it change the tree?"""
    r = git_run(repo, "merge-tree", "--write-tree", base, ref)
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    tree = lines[0] if lines and len(lines[0]) >= 40 else ""
    if r.returncode != 0 or not tree:
        return {"clean": False, "files": []}
    names = git(repo, "diff", "--name-only", base, tree)
    files = [l for l in names.splitlines() if l]
    return {"clean": True, "files": files, "tree": tree}


def cherry_unique(repo: Path, ref: str, base: str) -> list[dict]:
    if not git_ok(repo, "rev-parse", "--verify", ref):
        return []
    out = git(repo, "cherry", "-v", base, ref)
    unique = []
    for line in out.splitlines():
        if not line.startswith("+ "):
            continue
        parts = line[2:].split(" ", 1)
        sha = parts[0]
        subject = parts[1] if len(parts) > 1 else ""
        unique.append({"sha": sha, "subject": subject, "ref": ref})
    return unique


def stash_entries(repo: Path) -> list[dict]:
    raw = git(repo, "stash", "list")
    entries = []
    for i, line in enumerate(raw.splitlines()):
        ref = f"stash@{{{i}}}"
        msg = line.split(": ", 1)[-1] if ": " in line else line
        stat = git(repo, "stash", "show", "--stat", ref)
        superseded = "superseded" in msg.lower()
        entries.append(
            {
                "ref": ref,
                "message": msg,
                "stat": stat.splitlines()[-1] if stat else "",
                "drop": superseded,
            }
        )
    return entries


DEPLOY_FILES = (
    "wrangler.toml",
    "wrangler.jsonc",
    "wrangler.json",
    "firebase.json",
)


def ci_deploys(repo: Path) -> bool:
    workflows = repo / ".github" / "workflows"
    if not workflows.is_dir():
        return False
    for p in workflows.glob("*.yml"):
        text = p.read_text(errors="ignore")
        if "wrangler" in text and "deploy" in text:
            return True
    for p in workflows.glob("*.yaml"):
        text = p.read_text(errors="ignore")
        if "wrangler" in text and "deploy" in text:
            return True
    return False


def deploy_opted_out(repo: Path) -> bool:
    """True when CLAUDE.md says the repo is not a deploy target."""
    claude = repo / "CLAUDE.md"
    if not claude.is_file():
        return False
    return "not a deploy target" in claude.read_text(errors="ignore").lower()


def has_deploy_surface(repo: Path) -> bool:
    """True when the repo has wrangler, Firebase, or CI that deploys wrangler."""
    if ci_deploys(repo):
        return True
    return any((repo / name).is_file() for name in DEPLOY_FILES)


def plans_deploy(repo: Path) -> bool:
    """Plan a deploy only for a real host, never for local-only / housekeeping repos."""
    if not (repo / "CLAUDE.md").is_file():
        return False
    if deploy_opted_out(repo):
        return False
    return has_deploy_surface(repo)


def owned_rel(repo: Path, path: Path) -> bool:
    try:
        rel = os.path.relpath(path, repo)
    except ValueError:
        return False
    return any(rel == d or rel.startswith(d + os.sep) for d in OWNED_WT)


def remote_refs(repo: Path) -> list[str]:
    refs = []
    for line in git(repo, "branch", "-r").splitlines():
        name = line.strip()
        if not name or "->" in name or REMOTE_SKIP.search(name):
            continue
        refs.append(name)
    return refs


def local_refs(repo: Path, base: str) -> list[str]:
    refs = []
    for line in git(repo, "branch", "--format=%(refname:short)").splitlines():
        name = line.strip().lstrip("* ")
        if name and name != base:
            refs.append(name)
    return refs
