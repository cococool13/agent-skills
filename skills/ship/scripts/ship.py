#!/usr/bin/env python3
"""Inspect or ship the current branch. Deployment remains an agent operation."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from apply import APPLY_OPS, apply_actions
from gitleaks_check import run_preflight
from lib import bucket_file, current_repo, git, git_ok, git_run, parse_status, plans_deploy, suggest_msg


def inspect(repo: Path) -> dict:
    branch = git(repo, "branch", "--show-current")
    buckets = {"commit": [], "secret": [], "noise": [], "archive": []}
    blockers = []
    if not branch:
        blockers.append("detached HEAD; select the intended branch")
    for operation in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        location = git(repo, "rev-parse", "--git-path", operation)
        if location and (repo / location).exists():
            blockers.append("unfinished Git operation; resolve it before shipping")
            break
    for row in parse_status(repo):
        paths = [row["path"]] + ([row["source"]] if row.get("source") else [])
        kinds = [bucket_file(p, row["untracked"], repo) for p in paths]
        kind = next((k for k in kinds if k != "commit"), "commit")
        buckets[kind].extend(paths)
        if row["xy"] in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}:
            blockers.append("unmerged index entries")
    upstream = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") if git_ok(repo, "rev-parse", "@{u}") else ""
    ahead = behind = 0
    if upstream:
        counts = git_run(repo, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
        if counts.returncode or len(counts.stdout.split()) != 2:
            blockers.append("cannot compare upstream")
        else:
            ahead, behind = map(int, counts.stdout.split())
    remotes = git(repo, "remote").splitlines()
    remote = git(repo, "config", "--get", f"branch.{branch}.remote") if branch else ""
    merge_ref = git(repo, "config", "--get", f"branch.{branch}.merge") if branch else ""
    target = merge_ref.removeprefix("refs/heads/") if merge_ref else branch
    if not remote:
        remote = "origin" if "origin" in remotes else (remotes[0] if len(remotes) == 1 else "")
    if remote == "." or (merge_ref and not merge_ref.startswith("refs/heads/")):
        blockers.append("upstream is not a remote branch; choose the intended push destination")
    if remotes and not remote:
        blockers.append("multiple remotes without an upstream; choose the push destination")
    if remote and not upstream and branch:
        exists = git_ok(repo, "show-ref", "--verify", "--quiet", f"refs/remotes/{remote}/{target}")
        if exists:
            blockers.append("remote branch exists without tracking; configure upstream and inspect divergence")
    if behind:
        blockers.append("branch is behind upstream; integrate and validate the final code before apply")
    return dict(path=str(repo), branch=branch, buckets=buckets, upstream=upstream,
                ahead=ahead, behind=behind, remote=remote, target=target,
                blockers=list(dict.fromkeys(blockers)), deploy_hint=plans_deploy(repo))


def actions_for(info: dict) -> list[dict]:
    actions = []
    files = list(dict.fromkeys(info["buckets"]["commit"]))
    if files:
        actions.append(dict(op="commit", repo=info["path"], files=files, message=suggest_msg(files)))
    for kind, paths in info["buckets"].items():
        if kind != "commit" and paths:
            actions.append(dict(op="skip-files", repo=info["path"], kind=kind, files=paths))
    if info["remote"] and (files or info["ahead"] or not info["upstream"]):
        actions.append(dict(op="push", repo=info["path"], remote=info["remote"],
                            branch=info["target"], set_upstream=not bool(info["upstream"])))
    elif not info["remote"]:
        actions.append(dict(op="local-only", repo=info["path"]))
    if info["deploy_hint"]:
        actions.append(dict(op="deploy", repo=info["path"], mode="verify-project-instructions"))
    return actions


def build(skip_fetch: bool, plan_only: bool, *, fast: bool = False) -> dict:
    repo = current_repo()
    payload = dict(cwd=os.getcwd(), current=None, actions=[], blockers=[],
                   worktrees={"removed": 0}, gitleaks={"ok": None, "summary": "not run in plan mode"})
    if repo is None:
        payload["blockers"].append("not in a Git repository")
        return payload
    if not plan_only and not skip_fetch:
        # Fetch does not send commits. Only apply consults the network.
        result = git_run(repo, "fetch", "--all", "--prune", timeout=45)
        if result.returncode:
            payload["blockers"].append("fetch failed; remote state is not verified")
    info = inspect(repo)
    payload.update(current=info, actions=actions_for(info))
    payload["blockers"].extend(info["blockers"])
    if not plan_only and not payload["blockers"]:
        payload["gitleaks"] = run_preflight(repo)
        if not payload["gitleaks"]["ok"]:
            payload["blockers"].append(payload["gitleaks"]["summary"])
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="scan, commit and push current branch")
    mode.add_argument("--plan-only", action="store_true", help="local inspection only (default)")
    parser.add_argument("--skip-fetch", action="store_true", help="plan-mode compatibility; apply always fetches")
    parser.add_argument("--fast", action="store_true", help="compatibility; all plans inspect current branch only")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.apply and args.skip_fetch:
        parser.error("--skip-fetch is only valid for local plans")
    try:
        payload = build(skip_fetch=not args.apply, plan_only=not args.apply)
        payload["actions"] = apply_actions(payload["actions"], "apply" if args.apply and not payload["blockers"] else "none")
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        print("ship failed or timed out; inspect Git state before continuing; do not replay a push", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        info = payload["current"]
        print(f"SHIP: {info['path']} ({info['branch']})" if info else "SHIP: no repository")
        for blocker in payload["blockers"]:
            print(f"BLOCKED: {blocker}")
        print(f"scan: {payload['gitleaks']['summary']}")
        for action in payload["actions"]:
            print(f"{action['status']}: {action['op']}" + (f" — {action['error']}" if action.get("error") else ""))
    if payload["blockers"] or any(a["status"] == "failed" for a in payload["actions"]):
        return 1
    pending = any(a["op"] in APPLY_OPS | {"deploy", "local-only"} and a["status"] != "ok" for a in payload["actions"])
    return 2 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
