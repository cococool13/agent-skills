#!/usr/bin/env python3
"""Plan or ship the current branch: fetch, check, scan, commit, push. Never deploys."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PREFLIGHT = Path.home() / ".agents/skills/gitleaks-preflight/scripts/preflight.sh"
SECRET_RE = re.compile(
    r"(password|secret|credential|bitwarden|1password|lastpass|keepass|"
    r"recovery.?code|backup.?code|seed.?phrase|mnemonic|id_rsa|id_ed25519|"
    r"service-account|keychain|\.pem$|\.key$|\.p12$|(?:^|/)\.env(?:$|\.)|(?:^|/)\.envrc$|(?:^|/)\.dev\.vars$)",
    re.I,
)
# Committed templates. Real env files stay secret.
EXAMPLE_ENV_RE = re.compile(r"(?:^|/)\.env(?:\.[^/]+)*\.(?:example|sample|template)$", re.I)
NOISE_RE = re.compile(
    r"(?:^|/)\.DS_Store$|(?:^|/)Thumbs\.db$|\.pyc$|(?:^|/)__pycache__(?:/|$)|\.log$|"
    r"\.tsbuildinfo$|\.orig$|\.rej$|(?:^|/)\.claude/worktrees/|(?:^|/)\.worktrees/|"
    r"(?:^|/)\.turbo/|(?:^|/)coverage/|(?:^|/)node_modules(?:/|$)|(?:^|/)\.next(?:/|$)",
    re.I,
)
MAX_UNTRACKED = 5 * 1024 * 1024
OWNED_DIRS = (".claude/worktrees", ".worktrees", "worktrees")
TRASH = Path.home() / ".Trash"
WARN_BYTES = 50 * 1024 * 1024
BLOCK_BYTES = 100 * 1024 * 1024
LFS_POINTER = b"version https://git-lfs.github.com/spec"
UNMERGED = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
# Fail fast instead of hanging on a credential prompt.
NET_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def run(repo: Path, *args: str, timeout: int = 120, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True,
                          timeout=timeout, env=env)


def out(repo: Path, *args: str) -> str:
    return run(repo, *args).stdout.rstrip()


def ok(repo: Path, *args: str) -> bool:
    return run(repo, *args).returncode == 0


def human_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n // (1024 * 1024)} MB"
    return f"{n} bytes"


def lfs_stored(repo: Path, files: list[str]) -> set[str]:
    """Paths committed as LFS pointers. Working-tree size is not the stored blob."""
    if not files:
        return set()
    result = run(repo, "check-attr", "-z", "filter", "--", *files)
    parts = result.stdout.split("\0")
    marked = {parts[i] for i in range(0, len(parts) - 2, 3) if parts[i + 1] == "filter" and parts[i + 2] == "lfs"}
    if not marked:
        return set()
    if out(repo, "config", "--get", "filter.lfs.clean"):
        return marked
    pointers = set()
    for path in marked:
        try:
            with (repo / path).open("rb") as handle:
                if handle.read(len(LFS_POINTER)) == LFS_POINTER:
                    pointers.add(path)
        except OSError:
            pass
    return pointers


def bucket(path: str, untracked: bool, repo: Path) -> str:
    if not EXAMPLE_ENV_RE.search(path) and SECRET_RE.search(path):
        return "secret"
    if NOISE_RE.search(path):
        return "noise"
    if untracked and (path.startswith("_archive/") or "/_archive/" in path):
        return "archive"
    if untracked:
        try:
            if (repo / path).is_file() and (repo / path).stat().st_size > MAX_UNTRACKED:
                return "noise"
        except OSError:
            pass
    return "commit"


def status(repo: Path) -> list[dict]:
    result = run(repo, "status", "--porcelain=v1", "-z", "-uall")
    if result.returncode:
        raise RuntimeError("git status failed")
    entries, rows = iter(result.stdout.split("\0")), []
    for entry in entries:
        if entry:
            row = {"xy": entry[:2], "paths": [entry[3:]]}
            if "R" in row["xy"] or "C" in row["xy"]:
                row["paths"].append(next(entries))
            rows.append(row)
    return rows


def destination(repo: Path, branch: str) -> tuple[str, str, str]:
    """Return (remote, target branch, merge ref) for the branch."""
    remote = out(repo, "config", "--get", f"branch.{branch}.remote") if branch else ""
    merge_ref = out(repo, "config", "--get", f"branch.{branch}.merge") if branch else ""
    if not remote:
        remotes = out(repo, "remote").splitlines()
        remote = "origin" if "origin" in remotes else (remotes[0] if len(remotes) == 1 else "")
    return remote, merge_ref.removeprefix("refs/heads/") or branch, merge_ref


def inspect(repo: Path) -> dict:
    branch = out(repo, "branch", "--show-current")
    buckets = {"commit": [], "secret": [], "noise": [], "archive": []}
    blockers = []
    if not branch:
        blockers.append("detached HEAD; check out the intended branch")
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        if (repo / out(repo, "rev-parse", "--git-path", marker)).exists():
            blockers.append("unfinished merge, rebase, cherry-pick or revert")
            break
    for row in status(repo):
        kinds = [bucket(p, row["xy"] == "??", repo) for p in row["paths"]]
        buckets[next((k for k in kinds if k != "commit"), "commit")].extend(row["paths"])
        if row["xy"] in UNMERGED:
            blockers.append("unmerged index entries")
    staged = [p for p in run(repo, "diff", "--cached", "--name-only", "-z").stdout.split("\0") if p]
    remote, target, merge_ref = destination(repo, branch)
    remotes = out(repo, "remote").splitlines()
    upstream = out(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") if ok(repo, "rev-parse", "@{u}") else ""
    ahead = behind = 0
    if upstream:
        counts = out(repo, "rev-list", "--left-right", "--count", f"HEAD...{upstream}").split()
        if len(counts) == 2:
            ahead, behind = map(int, counts)
        else:
            blockers.append("cannot compare with upstream")
    unpushed = []
    if upstream and ahead:
        unpushed = [line for line in out(repo, "log", "--format=%h %s", "-n", "20", f"{upstream}..HEAD").splitlines() if line]
    if remote == "." or (merge_ref and not merge_ref.startswith("refs/heads/")):
        blockers.append("upstream is not a remote branch; set the intended push destination")
    elif remotes and not remote:
        blockers.append("several remotes and no upstream; set the push destination")
    elif remote and not upstream and branch and ok(repo, "show-ref", "--verify", "--quiet", f"refs/remotes/{remote}/{target}"):
        blockers.append(f"{remote}/{target} exists but is not tracked; set upstream and inspect divergence")
    if behind:
        blockers.append(f"behind {upstream} by {behind}; integrate, re-validate, then apply")
    return dict(path=str(repo), branch=branch, remote=remote, target=target, upstream=upstream,
                ahead=ahead, behind=behind, unpushed=unpushed, staged=staged, buckets=buckets,
                blockers=list(dict.fromkeys(blockers)))


def scan(repo: Path) -> dict:
    if not PREFLIGHT.is_file():
        return {"ok": False, "summary": "gitleaks preflight script missing"}
    try:
        result = subprocess.run(["bash", str(PREFLIGHT), str(repo)], capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "summary": "gitleaks preflight unavailable or timed out"}
    # Scanner output can contain secret values. Report only the verdict.
    if result.returncode == 0:
        return {"ok": True, "summary": "clean"}
    return {"ok": False, "summary": f"gitleaks preflight failed (exit {result.returncode}); use gitleaks-preflight"}


def commit(repo: Path, files: list[str], staged: list[str], messages: list[str]) -> str:
    """Commit exactly `files`. Return an error, or '' on success."""
    if set(staged) - set(files):
        return "index has staged paths outside the commit set; unstage them or name them"
    tracked = set(run(repo, "ls-files", "--cached", "-z").stdout.split("\0"))
    # A staged rename's old path is already gone from disk and index.
    to_add = [f for f in files if f in tracked or os.path.lexists(repo / f)]
    if to_add and run(repo, "--literal-pathspecs", "add", "--", *to_add).returncode:
        return "staging failed; inspect the index"
    if run(repo, "commit", *[a for m in messages for a in ("-m", m)]).returncode:
        return "commit failed; inspect hooks and the index"
    return ""


def plan(repo: Path, info: dict, paths: list[str], messages: list[str], apply: bool) -> tuple[list[dict], list[str], list[str]]:
    blockers = list(info["blockers"])
    changed = {p for kind in info["buckets"].values() for p in kind}
    if unknown := [p for p in paths if p not in changed]:
        blockers.append(f"not changed: {', '.join(unknown)}")
    if secret := [p for p in paths if p in info["buckets"]["secret"]]:
        blockers.append(f"secret-looking paths: {', '.join(secret)}")
    files = list(dict.fromkeys(paths or info["buckets"]["commit"]))
    if apply and files and not messages:
        blockers.append("commit message required: -m")
    warnings = []
    sized = []
    for path in files:
        file = repo / path
        try:
            if not file.is_file():
                continue
            size = file.stat().st_size
        except OSError:
            continue
        if size > WARN_BYTES:
            sized.append((path, size))
    stored = lfs_stored(repo, [path for path, _ in sized])
    for path, size in sized:
        if path in stored:
            continue
        if size > BLOCK_BYTES:
            blockers.append(f"{path} is {human_size(size)}; GitHub rejects files over {human_size(BLOCK_BYTES)}")
        else:
            warnings.append(f"{path} is {human_size(size)}; GitHub warns above {human_size(WARN_BYTES)}")
    ops = [{"op": "commit", "files": files}] if files else []
    if info["remote"] and (files or info["ahead"] or not info["upstream"]):
        ops.append({"op": "push", "remote": info["remote"], "target": info["target"],
                    "set_upstream": not info["upstream"]})
    if any(op.get("set_upstream") for op in ops):
        warnings.append("no upstream; push publishes this branch")
    return ops, blockers, warnings


def list_worktrees(repo: Path) -> list[dict]:
    rows, current = [], None
    for line in run(repo, "worktree", "list", "--porcelain", "-z").stdout.split("\0"):
        if line.startswith("worktree "):
            if current:
                rows.append(current)
            current = {"path": line[9:]}
        elif current is None or not line:
            continue
        elif line.startswith("branch "):
            current["branch"] = line[7:]
        elif line == "detached":
            current["detached"] = True
        elif line == "bare":
            current["bare"] = True
        elif line.startswith("locked"):
            current["locked"] = True
    if current:
        rows.append(current)
    return rows


def worktree_plan(repo: Path) -> list[dict]:
    """Other worktrees that are safe to remove. The main and current checkouts stay."""
    here = repo.resolve()
    items, seen = [], set()
    for row in list_worktrees(repo):
        path = Path(row["path"])
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        seen.add(resolved)
        item = {"path": str(path), "branch": row.get("branch", "")}
        if row.get("bare") or resolved == here or (path / ".git").is_dir():
            continue
        if not path.exists():
            items.append({**item, "action": "prune", "reason": "missing"})
        elif row.get("locked"):
            items.append({**item, "action": "keep", "reason": "locked"})
        else:
            status = run(path, "status", "--porcelain")
            head = out(path, "rev-parse", "HEAD") if status.returncode == 0 else ""
            if status.returncode or status.stdout.strip():
                items.append({**item, "action": "keep", "reason": "dirty" if status.stdout.strip() else "unknown"})
            elif not head or not ok(repo, "merge-base", "--is-ancestor", head, "HEAD"):
                items.append({**item, "action": "keep", "reason": "unique-commits"})
            else:
                items.append({**item, "action": "remove", "reason": "old"})
    for name in OWNED_DIRS:
        parent = repo / name
        if not parent.is_dir():
            continue
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            try:
                resolved = child.resolve()
            except OSError:
                resolved = child
            if resolved in seen:
                continue
            seen.add(resolved)
            item = {"path": str(child), "branch": ""}
            git_dir = child / ".git"
            if git_dir.exists():
                status = run(child, "status", "--porcelain")
                head = out(child, "rev-parse", "HEAD") if status.returncode == 0 else ""
                if status.returncode or status.stdout.strip():
                    items.append({**item, "action": "keep", "reason": "dirty" if status.stdout.strip() else "unknown"})
                    continue
                if head and not ok(repo, "merge-base", "--is-ancestor", head, "HEAD"):
                    items.append({**item, "action": "keep", "reason": "unique-commits"})
                    continue
            items.append({**item, "action": "trash", "reason": "leftover"})
    return items


def trash_dir(src: Path) -> str:
    root = TRASH / f"ship-worktrees-{datetime.now():%Y%m%d-%H%M%S}"
    root.mkdir(parents=True, exist_ok=True)
    dest, n = root / src.name, 1
    while dest.exists():
        dest = root / f"{src.name}-{n}"
        n += 1
    src.rename(dest)
    return str(dest)


def do_cleanup(repo: Path, items: list[dict]) -> dict:
    result = {"removed": [], "trashed": [], "branches": [], "kept": [], "failed": []}
    current = out(repo, "branch", "--show-current")
    for item in items:
        action, path = item["action"], Path(item["path"])
        if action == "keep":
            result["kept"].append(item)
            continue
        if action == "prune":
            continue
        if action == "remove":
            cmd = run(repo, "worktree", "remove", str(path))
            if cmd.returncode == 0 and not path.exists():
                result["removed"].append(str(path))
                name = item.get("branch", "").removeprefix("refs/heads/")
                if name and name != current and run(repo, "branch", "-d", name).returncode == 0:
                    result["branches"].append(name)
            else:
                result["failed"].append({"path": str(path), "reason": "remove-failed"})
            continue
        try:
            result["trashed"].append(trash_dir(path))
        except OSError:
            result["failed"].append({"path": str(path), "reason": "trash-failed"})
    run(repo, "worktree", "prune")
    remaining = {row["path"] for row in list_worktrees(repo)}
    for item in items:
        if item["action"] != "prune":
            continue
        if item["path"] in remaining:
            result["failed"].append({"path": item["path"], "reason": "prune-failed"})
        else:
            result["removed"].append(item["path"])
    for name in OWNED_DIRS:
        parent = repo / name
        if parent.is_dir() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError:
                pass
    return result


def ship(repo: Path | None, apply: bool, messages: list[str], paths: list[str]) -> dict:
    payload = dict(mode="apply" if apply else "plan", repo=None, blockers=[], warnings=[],
                   cleanup=[], scan=None, done=[], pending=[])
    if repo is None:
        payload["blockers"].append("not in a Git repository")
        return payload
    remote = destination(repo, out(repo, "branch", "--show-current"))[0]
    if remote and remote != "." and run(repo, "fetch", "--quiet", remote, timeout=60, env=NET_ENV).returncode:
        payload["blockers"].append(f"fetch {remote} failed; remote state unknown")
    info = inspect(repo)
    ops, blockers, warnings = plan(repo, info, paths, messages, apply)
    cleanup = worktree_plan(repo)
    if any(item["action"] != "keep" for item in cleanup):
        ops.append({"op": "cleanup"})
    payload.update(repo=info, pending=ops, warnings=warnings, cleanup=cleanup)
    payload["blockers"].extend(blockers)
    if not apply or payload["blockers"] or not ops:
        return payload

    if any(op["op"] != "cleanup" for op in payload["pending"]):
        payload["scan"] = scan(repo)
        if not payload["scan"]["ok"]:
            payload["blockers"].append(payload["scan"]["summary"])
            return payload
    while payload["pending"]:
        op = payload["pending"][0]
        if op["op"] == "commit":
            error = commit(repo, op["files"], info["staged"], messages)
        elif op["op"] == "cleanup":
            payload["cleanup_result"] = do_cleanup(repo, cleanup)
            error = "Worktree cleanup failed. The directories remain." if payload["cleanup_result"]["failed"] else ""
        else:
            push = ["push", *(["-u"] if op["set_upstream"] else []), op["remote"], f"HEAD:refs/heads/{op['target']}"]
            result = run(repo, *push, timeout=180, env=NET_ENV)
            # Remote and hook output can contain secrets. Do not echo it.
            error = f"push failed (exit {result.returncode}); check the remote revision before any retry" if result.returncode else ""
        if error:
            payload["blockers"].append(error)
            break
        payload["done"].append(dict(payload["pending"].pop(0), sha=out(repo, "rev-parse", "HEAD")))
    return payload


def current_repo() -> Path | None:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], text=True, capture_output=True)
    return Path(result.stdout.strip()) if result.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="scan, commit, push, and remove old worktrees")
    parser.add_argument("-m", "--message", action="append", default=[], help="commit message paragraph; repeatable")
    parser.add_argument("paths", nargs="*", help="exact paths to commit (default: the commit bucket)")
    args = parser.parse_args()
    try:
        payload = ship(current_repo(), args.apply, args.message, args.paths)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ship stopped ({type(exc).__name__}); inspect Git state and the remote revision before any retry",
              file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2))
    if payload["blockers"]:
        return 1
    return 2 if payload["pending"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
