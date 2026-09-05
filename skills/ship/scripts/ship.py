#!/usr/bin/env python3
"""Plan and apply /ship for the current git repo only. Leaves deploy to the agent."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from apply import apply_actions  # noqa: E402
from lib import (  # noqa: E402
    bucket_file,
    ci_deploys,
    current_repo,
    default_base,
    git,
    git_ok,
    git_run,
    is_ancestor,
    local_refs,
    merge_preview,
    parse_status,
    parse_worktrees,
    plans_deploy,
    remote_refs,
    stash_entries,
    suggest_msg,
)
from gitleaks_check import run_preflight  # noqa: E402
from sync import sync_agent_docs  # noqa: E402
from worktrees import cleanup_repo, empty_cleanup, format_cleanup, leftover_dirs  # noqa: E402


def fetch_one(repo: Path) -> tuple[str, str]:
    if not git(repo, "remote"):
        return str(repo), ""
    r = git_run(repo, "fetch", "--all", "--prune", timeout=45)
    err = (r.stderr or "").strip().splitlines()
    tail = err[-1] if err and r.returncode != 0 else ""
    return str(repo), tail


def inspect(repo: Path, extra_paths: list[Path], *, fast: bool = False) -> dict:
    base = default_base(repo)
    branch = git(repo, "branch", "--show-current") or "(detached)"
    status = parse_status(repo)
    buckets = {"commit": [], "secret": [], "noise": [], "archive": []}
    for row in status:
        buckets[bucket_file(row["path"], row["untracked"], repo)].append(row["path"])

    upstream = ""
    if git_ok(repo, "rev-parse", "@{u}"):
        upstream = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    ahead = behind = None
    if upstream:
        counts = git(repo, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
        parts = counts.split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])

    seen_tips: set[str] = set()
    integrate: list[dict] = []
    drop_local: list[str] = []
    keep_refs: list[dict] = []

    def consider(ref: str, kind: str) -> None:
        tip = git(repo, "rev-parse", ref)
        if not tip or tip in seen_tips:
            return
        seen_tips.add(tip)
        if is_ancestor(repo, ref, base):
            if kind == "local":
                drop_local.append(ref)
            return
        preview = merge_preview(repo, base, ref)
        if preview["clean"] and not preview["files"]:
            if kind == "local":
                drop_local.append(ref)
            return
        if preview["clean"] and preview["files"]:
            if len(preview["files"]) > 80:
                keep_refs.append(
                    {
                        "ref": ref,
                        "reason": f"clean merge but {len(preview['files'])} files — inspect",
                        "files": preview["files"][:20],
                    }
                )
                return
            integrate.append({"ref": ref, "files": preview["files"]})
            return
        keep_refs.append({"ref": ref, "reason": "merge into main would conflict (likely superseded)"})

    for ref in local_refs(repo, base):
        consider(ref, "local")
    if not fast:
        for ref in remote_refs(repo):
            consider(ref, "remote")

    extras = []
    for t in parse_worktrees(repo):
        p = t["path"]
        if p.resolve() == repo.resolve():
            continue
        row = {"path": str(p)}
        if "branch" in t:
            row["branch"] = t["branch"]
        if t.get("prunable"):
            row["prunable"] = True
        extras.append(row)
    for p in extra_paths:
        if str(p.resolve()) not in {e.get("path") for e in extras}:
            extras.append({"path": str(p), "prunable": True})

    remotes = git(repo, "remote").splitlines() if git(repo, "remote") else []
    return {
        "path": str(repo),
        "name": repo.name,
        "branch": branch,
        "base": base,
        "on_base": branch == base,
        "buckets": buckets,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "integrate": integrate,
        "drop_local": drop_local,
        "keep_refs": keep_refs,
        "stashes": stash_entries(repo),
        "extras": extras,
        "remotes": remotes,
        "has_claude": (repo / "CLAUDE.md").is_file(),
        "ci_deploys": ci_deploys(repo),
        "plans_deploy": plans_deploy(repo),
        "msg": suggest_msg(buckets["commit"]),
    }


def actions_for(info: dict, is_current: bool) -> list[dict]:
    repo = info["path"]
    acts: list[dict] = []
    commit_files = info["buckets"]["commit"]
    if commit_files:
        acts.append(
            {
                "op": "commit",
                "repo": repo,
                "files": commit_files,
                "message": info["msg"],
                "current": is_current,
            }
        )
    for path, kind in (
        (info["buckets"]["secret"], "secret"),
        (info["buckets"]["noise"], "noise"),
        (info["buckets"]["archive"], "archive"),
    ):
        if path:
            acts.append({"op": "skip-files", "repo": repo, "kind": kind, "files": path})

    for ref in info["drop_local"]:
        acts.append({"op": "branch-d", "repo": repo, "branch": ref})

    for stash in info["stashes"]:
        if stash["drop"]:
            acts.append({"op": "stash-drop", "repo": repo, "ref": stash["ref"], "message": stash["message"]})
        else:
            acts.append({"op": "keep-stash", "repo": repo, "ref": stash["ref"], "message": stash["message"]})

    for item in info["integrate"]:
        local = "/" not in item["ref"]
        acts.append(
            {
                "op": "merge",
                "repo": repo,
                "onto": info["base"],
                "from": item["ref"],
                "files": item.get("files", []),
                "delete_local_after": local,
            }
        )
    for item in info["keep_refs"]:
        acts.append({"op": "keep-ref", "repo": repo, **item})

    ahead, behind = info["ahead"], info["behind"]
    will_change_main = bool(commit_files or info["integrate"])
    if behind and (ahead or will_change_main):
        acts.append({"op": "rebase", "repo": repo, "upstream": info["upstream"]})
    elif behind:
        acts.append({"op": "ff", "repo": repo, "upstream": info["upstream"]})
    if info["upstream"] and (ahead or will_change_main):
        acts.append({"op": "push", "repo": repo, "upstream": info["upstream"]})
    elif will_change_main and not info["upstream"] and "origin" in info["remotes"]:
        acts.append({"op": "push", "repo": repo, "upstream": "origin", "set_upstream": True})
    elif will_change_main and not info["remotes"]:
        acts.append({"op": "local-only", "repo": repo})

    if is_current and info["plans_deploy"]:
        mode = "ci" if info["ci_deploys"] and info["on_base"] else "manual"
        acts.append({"op": "deploy", "repo": repo, "mode": mode, "ci": info["ci_deploys"]})
    return acts


AGENT_OPS = {"commit", "merge", "push", "ff", "rebase", "deploy"}


def _mark(action: dict) -> str:
    st = action.get("status")
    if st == "ok":
        return "ok "
    if st == "failed":
        return "FAIL "
    if st == "planned":
        return ""
    return ""


def human_plan(current: dict | None, actions: list[dict], cleanup: dict) -> str:
    counts = {}
    for a in actions:
        counts[a["op"]] = counts.get(a["op"], 0) + 1
    summary = "  ".join(
        f"{counts[k]} {k}"
        for k in ("commit", "merge", "push", "deploy", "keep-ref", "skip-files")
        if counts.get(k)
    )
    lines = ["SHIP PLAN", summary, ""]
    if current:
        lines.append(f"current: {current['path']}  ({current['branch']})")
    else:
        lines.append("current: none (not in a git repo — nothing to ship)")
    lines.append(format_cleanup(cleanup))
    lines.append("")

    groups = [
        ("COMMIT", "commit"),
        ("INTEGRATE onto main", "merge"),
        ("DROP equivalent local branch", "branch-d"),
        ("DROP superseded stash", "stash-drop"),
        ("FAST-FORWARD", "ff"),
        ("REBASE onto upstream", "rebase"),
        ("PUSH", "push"),
        ("DEPLOY", "deploy"),
        ("KEEP (do not delete)", "keep-ref"),
        ("KEEP stash", "keep-stash"),
        ("SKIP files", "skip-files"),
        ("LOCAL ONLY (no remote)", "local-only"),
    ]
    by_op: dict[str, list[dict]] = {}
    for a in actions:
        by_op.setdefault(a["op"], []).append(a)

    for title, op in groups:
        rows = by_op.get(op, [])
        if not rows:
            continue
        lines.append(f"{title} ({len(rows)})")
        for a in rows:
            name = Path(a["repo"]).name
            prefix = _mark(a)
            extra = a.get("error") or a.get("note") or ""
            extra = f"  {extra}" if extra else ""
            if op == "commit":
                lines.append(f"  {prefix}{name}: {len(a['files'])} files → {a['message']}{extra}")
            elif op == "merge":
                files = a.get("files") or []
                lines.append(f"  {prefix}{name}: merge {a['from']} → {a['onto']}  {len(files)} file(s){extra}")
            elif op == "branch-d":
                lines.append(f"  {prefix}{name}: {a['branch']}{extra}")
            elif op in {"stash-drop", "keep-stash"}:
                lines.append(f"  {prefix}{name}: {a['ref']}  {a.get('message', '')}{extra}")
            elif op in {"ff", "rebase", "push"}:
                flag = " -u" if a.get("set_upstream") else ""
                lines.append(f"  {prefix}{name}: {a.get('upstream') or ''}{flag}{extra}")
            elif op == "deploy":
                lines.append(f"  {prefix}{name}: {a['mode']}{extra}")
            elif op == "keep-ref":
                lines.append(f"  {prefix}{name}: {a['ref']}  {a['reason']}")
            elif op == "skip-files":
                lines.append(f"  {prefix}{name}: {a['kind']}  {len(a['files'])}  {', '.join(a['files'][:4])}")
            elif op == "local-only":
                lines.append(f"  {prefix}{name}")
        lines.append("")

    remaining = [a for a in actions if a["op"] in AGENT_OPS and a.get("status") in {None, "planned", "failed"}]
    failed = [a for a in actions if a.get("status") == "failed"]
    if failed:
        lines.append(f"failed: {len(failed)}")
    if remaining:
        lines.append(f"remaining: {len(remaining)} (deploy is agent-only; git should be applied with --apply)")
    else:
        lines.append("git is clean of planned mutations. KEEP/skip only, plus deploy if listed above.")
    return "\n".join(lines)


def build(skip_fetch: bool, plan_only: bool, *, fast: bool = False) -> dict:
    cur = current_repo()
    fetch_errors: dict[str, str] = {}
    if cur is None:
        return {
            "cwd": os.getcwd(),
            "current": None,
            "actions": [],
            "worktrees": empty_cleanup(),
            "fetch_errors": fetch_errors,
        }

    if not skip_fetch:
        print(f"fetching {cur.name}…", file=sys.stderr)
        path, err = fetch_one(cur)
        if err:
            fetch_errors[path] = err

    synced: list[dict] = []
    if plan_only:
        cleanup = empty_cleanup()
    else:
        print("syncing agent docs…", file=sys.stderr)
        synced = sync_agent_docs(cur)
        if synced:
            for row in synced:
                print(f"  synced {row['path']} from {row['from']}", file=sys.stderr)
        print("cleaning worktrees…", file=sys.stderr)
        cleanup = cleanup_repo(cur)

    print("inspecting…", file=sys.stderr)
    current = inspect(cur, leftover_dirs(cur), fast=fast)
    gitleaks = run_preflight(cur)
    if not gitleaks.get("ok"):
        print(f"gitleaks: {gitleaks.get('summary', 'failed')}", file=sys.stderr)
    return {
        "cwd": os.getcwd(),
        "current": current,
        "actions": actions_for(current, True),
        "worktrees": cleanup,
        "fetch_errors": fetch_errors,
        "synced_docs": synced,
        "gitleaks": gitleaks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan and apply /ship for the current git repo")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--fast", action="store_true", help="skip remote branch merge previews")
    parser.add_argument("--plan-only", action="store_true", help="no mutations")
    parser.add_argument("--apply", action="store_true", help="commit, merge, rebase, push (not deploy)")
    parser.add_argument("--json", action="store_true", help="JSON only")
    args = parser.parse_args()
    payload = build(skip_fetch=args.skip_fetch, plan_only=args.plan_only, fast=args.fast)
    if payload["current"] is None:
        mode = "none"
    elif args.plan_only:
        mode = "none"
    elif args.apply:
        mode = "apply"
        print("applying git…", file=sys.stderr)
    else:
        mode = "safe"
        print("applying safe git…", file=sys.stderr)
    payload["actions"] = apply_actions(payload["actions"], mode)

    remaining = [
        a
        for a in payload["actions"]
        if a["op"] in AGENT_OPS and a.get("status") in {None, "planned", "failed"}
    ]
    failed = [a for a in payload["actions"] if a.get("status") == "failed"]
    if args.json:
        json.dump(
            {
                "cwd": payload["cwd"],
                "current": payload["current"]["path"] if payload["current"] else None,
                "actions": payload["actions"],
                "worktrees": payload["worktrees"],
                "fetch_errors": payload["fetch_errors"],
            },
            sys.stdout,
            indent=2,
            default=str,
        )
        sys.stdout.write("\n")
    else:
        print(human_plan(payload["current"], payload["actions"], payload["worktrees"]))
    if payload["current"] is None:
        return 1
    if failed:
        return 1
    gl = payload.get("gitleaks") or {}
    if gl.get("ok") is False and not gl.get("skipped"):
        return 1
    if remaining:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
