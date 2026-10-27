#!/usr/bin/env python3
"""Plan or ship the current branch: fetch, scan, commit, integrate, push, verify. Never deploys."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ship_checks import discover, execute

SECRET_RE = re.compile(
    r"(password|secret|credential|bitwarden|1password|lastpass|keepass|"
    r"recovery.?code|backup.?code|seed.?phrase|mnemonic|id_rsa|id_ed25519|"
    r"service-account|keychain|(?:^|/)(?:auth|mcp_credentials)\.json$|\.netrc$|\.npmrc$|"
    r"\.p8$|\.pfx$|\.pem$|\.key$|\.p12$|(?:^|/)\.env(?:$|\.)|(?:^|/)\.envrc$|(?:^|/)\.dev\.vars$)",
    re.I,
)
# Committed templates. Real env files stay secret.
EXAMPLE_ENV_RE = re.compile(r"(?:^|/)\.env(?:\.[^/]+)*\.(?:example|sample|template)$", re.I)
SOURCE_SUFFIXES = {'.swift', '.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.go',
                   '.rs', '.java', '.kt', '.c', '.h', '.cpp', '.hpp', '.rb', '.sh', '.sql'}
PROTECTED_LOCATION = re.compile(r'(?:^|/)(?:\.env(?:$|\.)|\.dev\.vars|id_rsa|id_ed25519|\.ssh/|\.config/secrets/)', re.I)
NOISE_RE = re.compile(
    r"(?:^|/)\.DS_Store$|(?:^|/)Thumbs\.db$|\.pyc$|(?:^|/)__pycache__(?:/|$)|\.log$|"
    r"\.tsbuildinfo$|\.orig$|\.rej$|(?:^|/)\.claude/worktrees/|(?:^|/)\.worktrees/|"
    r"(?:^|/)\.turbo/|(?:^|/)coverage/|(?:^|/)node_modules(?:/|$)|(?:^|/)\.next(?:/|$)",
    re.I,
)
DEPLOY_RE = re.compile(r"wrangler|cloudflare|deploy", re.I)
MAX_UNTRACKED = 5 * 1024 * 1024
OWNED_DIRS = (".claude/worktrees", ".worktrees", "worktrees")
# A worktree touched this recently may belong to a live agent session.
RECENT_SECONDS = 72 * 3600
LIST_CAP = 20
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


def cap(items: list) -> list:
    return items if len(items) <= LIST_CAP else [*items[:LIST_CAP], f"... {len(items) - LIST_CAP} more"]


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
    # Credential-related source code is still source; gitleaks scans its contents.
    code = Path(path).suffix.lower() in SOURCE_SUFFIXES and not PROTECTED_LOCATION.search(path)
    if not code and not EXAMPLE_ENV_RE.search(path) and SECRET_RE.search(path):
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


def destination(repo: Path, branch: str, to: str = "") -> tuple[str, str, str]:
    """Return (remote, target branch, merge ref) for the branch."""
    remote = out(repo, "config", "--get", f"branch.{branch}.remote") if branch else ""
    merge_ref = out(repo, "config", "--get", f"branch.{branch}.merge") if branch else ""
    if not remote:
        remotes = out(repo, "remote").splitlines()
        remote = "origin" if "origin" in remotes else (remotes[0] if len(remotes) == 1 else "")
    return remote, to or merge_ref.removeprefix("refs/heads/") or branch, merge_ref


def deploy_hints(repo: Path) -> dict:
    """Where this repo's deploy is defined. Names only; the project AGENTS.md decides."""
    hints = {}
    workflows = repo / ".github" / "workflows"
    if workflows.is_dir():
        hints["ci"] = [str(p.relative_to(repo)) for p in sorted(workflows.glob("*.y*ml"))
                       if DEPLOY_RE.search(p.read_text(errors="ignore"))]
    try:
        scripts = json.loads((repo / "package.json").read_text()).get("scripts", {})
    except (OSError, ValueError, AttributeError):
        scripts = {}
    if names := [n for n in scripts if re.match(r"(deploy|release|ship)\b", n)]:
        pm = next((pm for lock, pm in (("pnpm-lock.yaml", "pnpm"), ("bun.lock", "bun"), ("bun.lockb", "bun"),
                                       ("yarn.lock", "yarn")) if (repo / lock).exists()), "npm")
        hints["scripts"] = [f"{pm} run {n}" for n in names]
    hints["wrangler"] = [str(p.relative_to(repo)) for pattern in ("wrangler.*", "*/wrangler.*")
                         for p in sorted(repo.glob(pattern))
                         if p.suffix in (".toml", ".json", ".jsonc") and "node_modules" not in p.parts]
    return {k: v for k, v in hints.items() if v}


def inspect(repo: Path, to: str = "") -> dict:
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
    remote, target, merge_ref = destination(repo, branch, to)
    remotes = out(repo, "remote").splitlines()
    upstream = out(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") if ok(repo, "rev-parse", "@{u}") else ""
    # The remote branch the push lands on; integrate against it, not the local upstream name.
    base = f"{remote}/{target}" if remote and ok(repo, "show-ref", "--verify", "--quiet", f"refs/remotes/{remote}/{target}") else ""
    ahead = behind = 0
    if base:
        counts = out(repo, "rev-list", "--left-right", "--count", f"HEAD...{base}").split()
        if len(counts) == 2:
            ahead, behind = map(int, counts)
        else:
            blockers.append(f"cannot compare with {base}")
    elif remote:
        ahead = int(out(repo, "rev-list", "--count", "HEAD", "--not", f"--remotes={remote}") or 0)
    unpushed = []
    if ahead:
        span = [f"{base}..HEAD"] if base else ["HEAD", "--not", f"--remotes={remote}"]
        unpushed = out(repo, "log", "--format=%h %s", "-n", str(LIST_CAP), *span).splitlines()
    if not to and (remote == "." or (merge_ref and not merge_ref.startswith("refs/heads/"))):
        blockers.append("upstream is not a remote branch; set the intended push destination")
    elif remotes and not remote:
        blockers.append("several remotes and no upstream; set the push destination")
    elif base and not to and base != upstream:
        blockers.append(f"{base} exists but is not tracked; pass --to {target} to ship onto it")
    default = out(repo, "symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD").removeprefix(f"{remote}/") if remote else ""
    return dict(path=str(repo), head=out(repo, 'rev-parse', 'HEAD'), branch=branch, remote=remote, target=target, base=base, upstream=upstream,
                default_branch=default, ahead=ahead, behind=behind, unpushed=unpushed, staged=staged,
                buckets=buckets, blockers=list(dict.fromkeys(blockers)))


def gitleaks_config(repo: Path) -> list[str]:
    for path in (repo / ".gitleaks.toml", Path.home() / ".config/gitleaks/config.toml"):
        if path.is_file():
            return ["--config", str(path)]
    return []


def scan(repo: Path, remote: str) -> dict:
    """Scan what this ship sends: the staged diff and commits the remote lacks. Report only the verdict."""
    exe = shutil.which("gitleaks")
    if not exe:
        return {"ok": False, "summary": "gitleaks not installed (brew install gitleaks)"}
    checks = {"staged": ["--staged"]}
    if remote:
        checks["unpushed"] = [f"--log-opts=HEAD --not --remotes={remote}"]
    for name, args in checks.items():
        try:
            result = subprocess.run([exe, "git", *args, *gitleaks_config(repo), "--redact", "--no-banner",
                                     "--exit-code", "1", "."], cwd=repo, capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired):
            return {"ok": False, "summary": f"gitleaks {name} scan did not finish"}
        # Scanner output can contain secret values. Report only the verdict.
        if result.returncode == 1:
            return {"ok": False, "summary": f"gitleaks found leaks in {name} changes; use gitleaks-preflight"}
        if result.returncode:
            return {"ok": False, "summary": f"gitleaks {name} scan failed (exit {result.returncode})"}
    return {"ok": True, "summary": "clean"}


def stage(repo: Path, files: list[str], staged: list[str]) -> str:
    """Stage exactly `files`. Return an error, or '' on success."""
    if set(staged) - set(files):
        return "index has staged paths outside the commit set; unstage them or name them"
    tracked = set(run(repo, "ls-files", "--cached", "-z").stdout.split("\0"))
    # A staged rename's old path is already gone from disk and index.
    to_add = [f for f in files if f in tracked or os.path.lexists(repo / f)]
    if to_add and run(repo, "--literal-pathspecs", "add", "--", *to_add).returncode:
        return "staging failed; inspect the index"
    return ""


def integrate(repo: Path, base: str) -> tuple[int, str]:
    """Rebase local commits onto `base`. Return (upstream commits taken, error)."""
    behind = int(out(repo, "rev-list", "--count", f"HEAD..{base}") or 0)
    if not behind:
        return 0, ""
    if out(repo, "rev-list", "--merges", f"{base}..HEAD"):
        return 0, f"unpushed merge commits; integrate {base} by hand"
    stashes = out(repo, "stash", "list")
    if run(repo, "rebase", "--autostash", base, timeout=300).returncode:
        run(repo, "rebase", "--abort")
        return 0, f"rebase onto {base} conflicts; aborted, integrate by hand"
    if out(repo, "stash", "list") != stashes:
        return behind, "rebased, but other local edits did not reapply; they are in stash@{0}"
    return behind, ""


def plan(repo: Path, info: dict, paths: list[str], messages: list[str], apply: bool) -> tuple[list[dict], list[str], list[str]]:
    blockers = list(info["blockers"])
    changed = {p for kind in info["buckets"].values() for p in kind}
    if unknown := [p for p in paths if p not in changed]:
        blockers.append(f"not changed: {', '.join(unknown)}")
    if secret := [p for p in paths if p in info["buckets"]["secret"]]:
        blockers.append(f"secret-looking paths: {', '.join(secret)}")
    if excluded := [p for p in paths if p in info["buckets"]["noise"] or p in info["buckets"]["archive"]]:
        blockers.append(f"excluded paths: {', '.join(excluded)}")
    # Apply without -m or paths never commits: it pushes what is already committed.
    push_only = apply and not paths and not messages
    files = [] if push_only else list(dict.fromkeys(paths or info["buckets"]["commit"]))
    if files and set(info['staged']) - set(files):
        blockers.append('index has staged paths outside the commit set; unstage them or name them')
    if apply and files and not messages:
        blockers.append("commit message required: -m")
    warnings = []
    if push_only and info["buckets"]["commit"]:
        warnings.append(f"{len(info['buckets']['commit'])} changed file(s) not committed; pass -m to commit")
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
    if info["behind"] and (files or info["ahead"]):
        ops.append({"op": "integrate", "base": info["base"], "behind": info["behind"]})
    if info["remote"] and (files or info["ahead"] or not info["base"]):
        set_upstream = not info["upstream"] and info["target"] == info["branch"]
        ops.append({"op": "push", "remote": info["remote"], "target": info["target"], "set_upstream": set_upstream})
        if not info["base"]:
            warnings.append(f"{info['remote']}/{info['target']} does not exist; push publishes it")
    return ops, blockers, warnings


def verify_remote(repo: Path, remote: str, target: str) -> dict:
    """Read remote state once; never retry a push with an uncertain outcome."""
    result = dict(remote=remote, target=target, local_sha=out(repo, "rev-parse", "HEAD"),
                  verified=False)
    if not remote or remote == "." or not target:
        return {**result, "status": "no_remote"}
    try:
        response = run(repo, "ls-remote", "--exit-code", remote, f"refs/heads/{target}",
                       timeout=60, env=NET_ENV)
    except (OSError, subprocess.TimeoutExpired):
        return {**result, "status": "unknown"}
    if response.returncode == 2:
        return {**result, "status": "missing"}
    if response.returncode:
        return {**result, "status": "unknown"}
    fields = response.stdout.split()
    if len(fields) != 2 or fields[1] != f"refs/heads/{target}":
        return {**result, "status": "unknown"}
    result.update(remote_sha=fields[0], verified=fields[0] == result['local_sha'])
    result['status'] = 'matches' if result['verified'] else 'differs'
    return result


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


def recent(path: Path) -> bool:
    """True if the checkout or its Git index, HEAD, or reflog changed within RECENT_SECONDS."""
    git_dir = out(path, "rev-parse", "--absolute-git-dir") if (path / ".git").exists() else ""
    paths = [path, *(Path(git_dir) / name for name in ("index", "HEAD", "logs/HEAD") if git_dir)]
    newest = max((p.stat().st_mtime for p in paths if p.exists()), default=0)
    return time.time() - newest < RECENT_SECONDS


def checkout_state(repo: Path, path: Path) -> str:
    """'' when a checkout is clean and merged into HEAD, else the reason to keep it."""
    status = run(path, "status", "--porcelain")
    if status.returncode or status.stdout.strip():
        return "dirty" if status.stdout.strip() else "unknown"
    head = out(path, "rev-parse", "HEAD")
    if head and not ok(repo, "merge-base", "--is-ancestor", head, "HEAD"):
        return "unique-commits"
    return "" if head else "unknown"


def worktree_plan(repo: Path) -> list[dict]:
    """Other worktrees that are safe to remove. The main, current, and recent checkouts stay."""
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
        elif recent(path):
            items.append({**item, "action": "keep", "reason": "recent"})
        elif reason := checkout_state(repo, path):
            items.append({**item, "action": "keep", "reason": reason})
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
            if recent(child):
                items.append({**item, "action": "keep", "reason": "recent"})
            elif (child / ".git").exists() and (reason := checkout_state(repo, child)):
                items.append({**item, "action": "keep", "reason": reason})
            else:
                items.append({**item, "action": "trash", "reason": "leftover"})
    return items


def scanned(repo: Path, remote: str, payload: dict) -> str:
    result = scan(repo, remote)
    payload["scan"] = result["summary"]
    return "" if result["ok"] else result["summary"]


def clean_messages(messages: list[str]) -> list[str]:
    """Remove AI co-author trailers while retaining human attribution."""
    ai_names = {'claude', 'codex', 'openai codex', 'chatgpt', 'openai', 'anthropic',
                'github copilot', 'copilot', 'grok', 'gemini', 'cursor', 'aider',
                'devin', 'windsurf', 'replit agent'}
    cleaned = []
    for message in messages:
        lines = []
        for line in message.splitlines():
            trailer = re.match(r'^\s*co-authored?-by\s*:\s*(.*?)\s*(?:<([^>]+)>)?\s*$', line, re.I)
            if trailer:
                name, email = trailer.groups()
                name = re.sub(r'\s+', ' ', name.casefold()).removesuffix(' [bot]')
                bot_email = re.fullmatch(r'(?:noreply|claude|codex|chatgpt|copilot|grok|gemini|cursor)@(?:anthropic\.com|openai\.com|cursor\.com|x\.ai)', email or '', re.I)
                if name in ai_names or name.startswith(('claude code', 'claude opus', 'claude sonnet', 'claude haiku')) or bot_email:
                    continue
            lines.append(line)
        text = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()
        if text:
            cleaned.append(text)
    return cleaned


def step(repo: Path, op: dict, info: dict, messages: list[str], payload: dict) -> str:
    """Run one pending op. Return an error, or '' on success."""
    if op["op"] == "commit":
        messages = clean_messages(messages)
        if not messages:
            return 'commit summary required after removing AI attribution'
        index = Path(out(repo, "rev-parse", "--git-path", "index"))
        if not index.is_absolute():
            index = repo / index
        with tempfile.TemporaryDirectory(prefix="ship-index-") as directory:
            backup = Path(directory) / "index"
            if index.exists():
                shutil.copy2(index, backup)
            error = stage(repo, op["files"], info["staged"])
            if not error:
                error = scanned(repo, info["remote"], payload)
            if error:
                if backup.exists():
                    shutil.copy2(backup, index)
                else:
                    index.unlink(missing_ok=True)
                return error
        if run(repo, "commit", *[a for m in messages for a in ("-m", m)]).returncode:
            return "commit failed; run the project's format and lint checks, then inspect hooks"
        committed = out(repo, 'log', '-1', '--format=%B')
        if any(not clean_messages([line]) for line in committed.splitlines()
               if re.match(r'^\s*co-authored?-by\s*:', line, re.I)):
            return 'commit hook added AI co-author attribution; correct the hook and local commit before pushing'
        return ""
    if op["op"] == "integrate":
        taken, error = integrate(repo, op["base"])
        if taken and not error:
            payload["revalidate"] = f"took {taken} upstream commit(s) from {op['base']}; re-run checks, then apply again"
        return error
    if op["op"] == "push":
        # A commit hook can change the committed tree after the staging scan.
        if error := scanned(repo, op["remote"], payload):
            return error
        push = ["push", *(["-u"] if op["set_upstream"] else []), op["remote"], f"HEAD:refs/heads/{op['target']}"]
        try:
            result = run(repo, *push, timeout=180, env=NET_ENV)
        except (OSError, subprocess.TimeoutExpired):
            payload['remote_check'] = verify_remote(repo, op['remote'], op['target'])
            payload['verified'] = payload['remote_check']['verified']
            payload['push_outcome'] = 'uncertain'
            return "push interrupted; read remote_check before any retry (hooks and CI may still be incomplete)"
        # Remote and hook output can contain secrets. Do not echo it.
        if result.returncode:
            payload['remote_check'] = verify_remote(repo, op['remote'], op['target'])
            payload['verified'] = payload['remote_check']['verified']
            return f"push failed (exit {result.returncode}); check the remote revision before any retry"
        payload['remote_check'] = verify_remote(repo, op['remote'], op['target'])
        payload["verified"] = payload['remote_check']['verified']
        return "" if payload["verified"] else "remote SHA differs from HEAD after push; inspect before any retry"
    return "unknown operation; nothing executed"


def ship(repo: Path | None, apply: bool, messages: list[str], paths: list[str], to: str = "",
         skip_fetch: bool = False, checks: list[str] | None = None,
         check_only: bool = False, check_timeout: int = 900, cleanup_report: bool = False) -> dict:
    payload = dict(mode="apply" if apply else "plan", blockers=[], warnings=[], pending=[], done=[])
    if repo is None:
        payload["blockers"].append("not in a Git repository")
        return payload
    if apply and skip_fetch:
        payload['blockers'].append('--skip-fetch is inspection-only; Apply requires fresh remote state')
        return payload
    remote = destination(repo, out(repo, "branch", "--show-current"))[0]
    if (not skip_fetch and not check_only and remote and remote != "."
            and run(repo, "fetch", "--quiet", remote, timeout=60, env=NET_ENV).returncode):
        payload["blockers"].append(f"fetch {remote} failed; remote state unknown")
    info = inspect(repo, to)
    ops, blockers, warnings = plan(repo, info, paths, messages, apply)
    cleanup = worktree_plan(repo) if cleanup_report else []
    # Shipping does not authorize deleting branches, worktrees or leftovers.
    # Keep candidates visible; cleanup needs a separately reviewed selection.
    repo_info = {k: v for k, v in info.items() if k != "blockers" and (v or k in ("ahead", "behind"))}
    repo_info["buckets"] = {k: cap(v) for k, v in info["buckets"].items() if v}
    payload.update(pending=ops, warnings=warnings, cleanup=cleanup, deploy=deploy_hints(repo), repo=repo_info,
                   check_candidates=discover(repo))
    payload["blockers"].extend(blockers)
    if check_only:
        payload['mode'] = 'check'
        payload['blockers'] = list(info['blockers'])
    if apply and ops and payload.get('check_candidates') and not checks:
        payload['blockers'].append('review check_candidates and pass required commands with --check')
    push_only_checks = apply and not messages and not paths and bool(checks)
    if push_only_checks and any(row['xy'] != '??' for row in status(repo)):
        payload['blockers'].append('push-only checks require a clean tracked tree; preserve local edits and validate committed HEAD')
    if (apply and ops or check_only) and not payload['blockers'] and checks:
        checked_head = out(repo, 'rev-parse', 'HEAD')
        payload['checks'], error = execute(repo, checks, check_timeout)
        if error:
            payload['blockers'].append(error)
        elif (checked_head != out(repo, 'rev-parse', 'HEAD')
              or info['branch'] != out(repo, 'branch', '--show-current')):
            payload['blockers'].append('HEAD or branch changed during checks; plan again')
        # Formatters and generated files can change the commit set.
        if not payload['blockers']:
            fresh = inspect(repo, to)
            if (fresh['remote'], fresh['target']) != (info['remote'], info['target']):
                payload['blockers'].append('push destination changed during checks; plan again')
            if push_only_checks and any(row['xy'] != '??' for row in status(repo)):
                payload['blockers'].append('checks changed tracked files; review and commit them before pushing')
            info = fresh
            ops, blockers, warnings = plan(repo, info, paths, messages, apply)
            payload.update(pending=ops)
            payload['blockers'].extend(blockers)
            payload['warnings'].extend(warnings)
    if check_only:
        if not checks:
            payload['blockers'].append('check-only requires at least one --check command')
        return payload
    if apply and not payload["blockers"]:
        while payload["pending"]:
            op = payload["pending"][0]
            try:
                error = step(repo, op, info, messages, payload)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                payload['interrupted'] = op['op']
                error = f"{op['op']} interrupted ({type(exc).__name__}); inspect Git state before any retry"
            if error:
                payload["blockers"].append(error)
                break
            payload["done"].append(dict(payload["pending"].pop(0), sha=out(repo, "rev-parse", "HEAD")))
            if "revalidate" in payload:
                break
        payload["left"] = cap([p for row in status(repo) for p in row["paths"]])
    return {k: v for k, v in payload.items() if v or k in ("blockers", "warnings", "pending", "done")}


def current_repo() -> Path | None:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], text=True, capture_output=True)
    return Path(result.stdout.strip()) if result.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--apply", action="store_true", help="scan, commit, integrate, push, verify (never cleanup)")
    modes.add_argument("--verify-only", action="store_true", help="read remote SHA without fetching, committing or pushing")
    modes.add_argument("--check-only", action="store_true", help="run --check commands without committing or pushing")
    modes.add_argument('--status', action='store_true', help='read the saved repository release journal')
    parser.add_argument('--all', action='store_true', help='consolidate all branches and worktrees, validate main, push and release')
    parser.add_argument('--resume', action='store_true', help='reconcile and resume the saved repo-wide release')
    parser.add_argument('--profile', default='', help='reviewed ship.toml in this repository or Git ship state')
    parser.add_argument('--new-release', action='store_true', help='deliberately release an unchanged completed commit again; never overrides an uncertain run')
    parser.add_argument("--check", action="append", default=[], help="reviewed check command, no shell; repeatable")
    parser.add_argument("--check-timeout", type=int, default=900, help="seconds per check (default: 900)")
    parser.add_argument("--cleanup-report", action="store_true", help="include worktree cleanup candidates; never removes them")
    parser.add_argument("--plan-only", action="store_true", help="plan only; this is the default")
    parser.add_argument("--skip-fetch", action="store_true", help="do not fetch before planning")
    parser.add_argument("--json", action="store_true", help="print JSON; this is the default")
    parser.add_argument("-m", "--message", action="append", default=[], help="commit message paragraph; repeatable")
    parser.add_argument("--to", default="", help="remote branch to ship onto (default: the upstream)")
    parser.add_argument("paths", nargs="*", help="exact paths to commit (default: the commit bucket)")
    args = parser.parse_args()
    if args.check_timeout < 1:
        parser.error('--check-timeout must be positive')
    if args.new_release and (not args.all or not args.apply or args.resume):
        parser.error('--new-release requires --all --apply and never replays an unfinished run')
    if args.plan_only and (args.apply or args.check_only or args.verify_only):
        print(json.dumps({"mode": "apply", "blockers": ["--plan-only and the selected mode contradict; run one of them"],
                          "warnings": [], "pending": [], "done": []}, separators=(",", ":")))
        return 1
    try:
        repo = current_repo()
        if args.all or args.status or args.resume:
            if args.paths or args.to or args.check or args.check_only or args.verify_only or args.skip_fetch:
                parser.error('repository mode uses its release profile, not task-scoped flags')
            from ship_all import repository_release
            payload = repository_release(repo, apply=args.apply or args.resume, resume=args.resume,
                                         status_only=args.status, filename=args.profile,
                                         note='\n\n'.join(args.message or []), new_release=args.new_release)
        elif args.verify_only:
            if repo is None:
                payload = {'mode': 'verify', 'blockers': ['not in a Git repository']}
            else:
                remote, target, _ = destination(repo, out(repo, 'branch', '--show-current'), args.to)
                payload = {'mode': 'verify', **verify_remote(repo, remote, target), 'blockers': []}
                if not payload['verified']:
                    payload['blockers'].append('remote does not confirm HEAD; inspect status before any retry')
        else:
            payload = ship(repo, args.apply, args.message, args.paths, args.to, skip_fetch=args.skip_fetch,
                           checks=args.check, check_only=args.check_only, check_timeout=args.check_timeout,
                           cleanup_report=args.cleanup_report)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'mode': 'apply' if args.apply else 'plan', 'blockers': [
            f'ship stopped ({type(exc).__name__}); inspect Git state and remote before any retry'],
            'warnings': [], 'pending': [], 'done': []}))
        return 1
    print(json.dumps(payload, separators=(",", ":")))
    if payload["blockers"]:
        return 1
    return 2 if payload.get("pending") and payload['mode'] not in ('check', 'verify') else 0


if __name__ == "__main__":
    raise SystemExit(main())
