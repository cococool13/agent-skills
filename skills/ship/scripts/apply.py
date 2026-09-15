#!/usr/bin/env python3
"""Apply current-branch shipping operations, stopping on the first failure."""
import os
from pathlib import Path

from lib import git_run

APPLY_OPS = {"commit", "ff", "rebase", "push"}


def _ok(action: dict, note: str = "") -> dict:
    return dict(action, status="ok", **({"note": note} if note else {}))


def _fail(action: dict, err: str) -> dict:
    return dict(action, status="failed", error=err)


def stage_commit(repo: Path, files: list[str], message: str) -> tuple[list[str], list[str], str]:
    # Do not absorb pre-existing staged paths outside the reviewed commit set.
    index = git_run(repo, "diff", "--cached", "--name-only", "-z")
    if index.returncode:
        return [], [], "cannot inspect index"
    unexpected = set(index.stdout.split("\0")) - {""} - set(files)
    if unexpected:
        return [], [], "index contains paths outside the commit set; review index before shipping"
    if not files:
        return [], [], "no files selected"
    tracked = git_run(repo, "ls-files", "--cached", "-z")
    if tracked.returncode:
        return [], files, "cannot inspect tracked paths"
    tracked_paths = set(tracked.stdout.split("\0"))
    # A staged rename's old path is already removed from the index.
    to_stage = [f for f in files if f in tracked_paths or os.path.lexists(repo / f)]
    if to_stage:
        result = git_run(repo, "--literal-pathspecs", "add", "--", *to_stage)
        if result.returncode:
            return [], files, "staging failed; inspect index before retrying"
    result = git_run(repo, "commit", "-m", message)
    if result.returncode:
        return files, [], "commit failed; inspect local hook or Git diagnostics"
    return files, [], ""


def apply_one(action: dict) -> dict:
    repo, op = Path(action["repo"]), action["op"]
    if op == "commit":
        staged, _, err = stage_commit(repo, action["files"], action["message"])
        return _fail(action, err) if err else _ok(action, f"staged {len(staged)}")
    if op in {"ff", "rebase"}:
        status = git_run(repo, "status", "--porcelain")
        if status.returncode or status.stdout:
            return _fail(action, "working tree must be clean before integration")
        command = ("merge", "--ff-only") if op == "ff" else ("rebase",)
        result = git_run(repo, *command, action["upstream"])
    elif op == "push":
        # Explicit destination avoids push.default and remote push-refspec surprises.
        command = ["push"]
        if action.get("set_upstream"):
            command.append("-u")
        result = git_run(repo, *command, action["remote"], f"HEAD:refs/heads/{action['branch']}")
    else:
        return _fail(action, "unsupported operation")
    if result.returncode:
        # Raw hook/remote diagnostics may contain secret values. Do not echo them.
        return _fail(action, f"{op} failed (exit {result.returncode}); inspect state before continuing")
    return _ok(action)


def apply_actions(actions: list[dict], mode: str) -> list[dict]:
    out, failed = [], False
    for action in actions:
        if mode != "apply" or action["op"] not in APPLY_OPS:
            out.append(dict(action, status="planned"))
        elif failed:
            out.append(dict(action, status="blocked", error="earlier operation failed"))
        else:
            result = apply_one(action)
            failed = result["status"] == "failed"
            out.append(result)
    return out
