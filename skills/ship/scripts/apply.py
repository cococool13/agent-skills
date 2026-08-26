#!/usr/bin/env python3
"""Apply /ship actions. Never force-push. Never --no-verify. Never print secrets."""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

from lib import git, git_ok, git_run, github_noreply_identity, looks_secret

SAFE_OPS = {"branch-d", "stash-drop", "ff"}
APPLY_OPS = SAFE_OPS | {"commit", "merge", "rebase", "push"}
ORDER = ["commit", "stash-drop", "merge", "ff", "rebase", "branch-d", "push"]


def _ok(action: dict, note: str = "") -> dict:
    action = dict(action)
    action["status"] = "ok"
    if note:
        action["note"] = note
    return action


def _fail(action: dict, err: str) -> dict:
    action = dict(action)
    action["status"] = "failed"
    lines = [ln for ln in (err or "").strip().splitlines() if ln.strip()]
    interesting = [ln for ln in lines if "GH007" in ln or "remote rejected" in ln or ln.startswith("error:")]
    picked = interesting[-1] if interesting else (lines[-1] if lines else "failed")
    action["error"] = picked[:240]
    return action


def stage_commit(repo: Path, files: list[str], message: str) -> tuple[list[str], list[str], str]:
    staged, skipped = [], []
    for f in files:
        p = repo / f
        if p.is_file():
            try:
                text = p.read_text(errors="ignore")[:200_000]
            except OSError:
                text = ""
            if looks_secret(text):
                skipped.append(f)
                continue
        r = git_run(repo, "add", "--", f)
        if r.returncode != 0:
            skipped.append(f)
            continue
        staged.append(f)
    if not staged:
        return staged, skipped, ""
    r = git_run(repo, "commit", "-m", message)
    if r.returncode != 0:
        return staged, skipped, (r.stderr or r.stdout or "commit failed")
    return staged, skipped, ""


def merge_onto(repo: Path, onto: str, src: str) -> tuple[bool, str]:
    branch = git(repo, "branch", "--show-current")
    dirty = git(repo, "status", "--porcelain")
    if branch == onto and not dirty:
        r = git_run(repo, "merge", "--no-edit", src)
        if r.returncode == 0:
            return True, ""
        git_run(repo, "merge", "--abort")
        return False, r.stderr or r.stdout or "merge conflict"
    wt = repo / ".worktrees" / "ship-integrate"
    if wt.exists():
        git_run(repo, "worktree", "remove", "--force", str(wt))
    r = git_run(repo, "worktree", "add", str(wt), onto)
    if r.returncode != 0:
        return False, r.stderr or "worktree add failed"
    r = git_run(wt, "merge", "--no-edit", src)
    if r.returncode != 0:
        git_run(wt, "merge", "--abort")
        git_run(repo, "worktree", "remove", "--force", str(wt))
        return False, r.stderr or r.stdout or "merge conflict"
    if git_ok(wt, "rev-parse", "@{u}"):
        p = git_run(wt, "push")
    else:
        p = git_run(wt, "push", "-u", "origin", onto)
    git_run(repo, "worktree", "remove", "--force", str(wt))
    git_run(repo, "branch", "-d", "ship-integrate")
    if p.returncode != 0:
        return False, p.stderr or "push after merge failed"
    return True, ""


def rewrite_unpushed_noreply(repo: Path) -> str:
    """Rewrite unpushed committer/author to GitHub noreply. No git-config writes."""
    ident = github_noreply_identity()
    if not ident or not git_ok(repo, "rev-parse", "@{u}"):
        return ""
    ahead = git(repo, "rev-list", "--left-right", "--count", "HEAD...@{u}").split()
    if len(ahead) != 2 or int(ahead[0]) == 0:
        return ""
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = ident[0]
    env["GIT_AUTHOR_EMAIL"] = ident[1]
    env["GIT_COMMITTER_NAME"] = ident[0]
    env["GIT_COMMITTER_EMAIL"] = ident[1]
    r = git_run(
        repo,
        "rebase",
        "--rebase-merges",
        "--exec",
        "git commit --amend --reset-author --no-edit",
        "@{u}",
        timeout=180,
        env=env,
    )
    if r.returncode == 0:
        return ""
    git_run(repo, "rebase", "--abort")
    return r.stderr or r.stdout or "could not rewrite unpushed identity"


def apply_one(action: dict) -> dict:
    repo = Path(action["repo"])
    op = action["op"]
    if op == "commit":
        staged, skipped, err = stage_commit(repo, action["files"], action["message"] or "chore: ship pending work")
        if err:
            return _fail(action, err)
        note = f"staged {len(staged)}"
        if skipped:
            note += f", skipped {len(skipped)} secret/failed"
        return _ok(action, note)
    if op == "stash-drop":
        r = git_run(repo, "stash", "drop", action["ref"])
        return _ok(action) if r.returncode == 0 else _fail(action, r.stderr or r.stdout)
    if op == "branch-d":
        r = git_run(repo, "branch", "-d", action["branch"])
        return _ok(action) if r.returncode == 0 else _fail(action, r.stderr or r.stdout)
    if op == "ff":
        if git(repo, "status", "--porcelain"):
            return _fail(action, "dirty; skipped fast-forward")
        r = git_run(repo, "merge", "--ff-only", "@{u}")
        return _ok(action) if r.returncode == 0 else _fail(action, r.stderr or r.stdout)
    if op == "rebase":
        if git(repo, "status", "--porcelain"):
            return _fail(action, "dirty; skipped rebase")
        r = git_run(repo, "rebase", "@{u}")
        if r.returncode == 0:
            return _ok(action)
        git_run(repo, "rebase", "--abort")
        return _fail(action, r.stderr or r.stdout or "rebase conflict")
    if op == "merge":
        ok, err = merge_onto(repo, action["onto"], action["from"])
        if not ok:
            return _fail(action, err)
        if action.get("delete_local_after"):
            git_run(repo, "branch", "-d", action["from"])
        return _ok(action)
    if op == "push":
        rewrite_err = rewrite_unpushed_noreply(repo)
        if rewrite_err:
            return _fail(action, rewrite_err)
        if action.get("set_upstream"):
            r = git_run(repo, "push", "-u", "origin", "HEAD")
        else:
            r = git_run(repo, "push")
        return _ok(action) if r.returncode == 0 else _fail(action, r.stderr or r.stdout)
    action = dict(action)
    action["status"] = "skipped"
    return action


def apply_actions(actions: list[dict], mode: str) -> list[dict]:
    """mode: safe | apply | none"""
    if mode == "none":
        return [dict(a, status="planned") for a in actions]
    allowed = APPLY_OPS if mode == "apply" else SAFE_OPS
    grouped: dict[str, list[dict]] = defaultdict(list)
    passthrough: list[dict] = []
    for a in actions:
        if a["op"] in allowed:
            grouped[a["repo"]].append(a)
        else:
            passthrough.append(dict(a, status="planned"))
    out: list[dict] = []
    for repo, acts in grouped.items():
        committed = False
        seq = []
        seen_multi = {"branch-d", "stash-drop"}
        used = set()
        for op in ORDER:
            for a in acts:
                if a["op"] == op and (op in seen_multi or op not in used):
                    seq.append(a)
                    if op not in seen_multi:
                        used.add(op)
        for a in seq:
            if a["op"] == "ff" and committed:
                a = dict(a, op="rebase")
            result = apply_one(a)
            if a["op"] == "commit" and result.get("status") == "ok":
                committed = True
            out.append(result)
    return out + passthrough
