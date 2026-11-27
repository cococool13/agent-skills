#!/usr/bin/python3
"""Shared Stop gate for Claude Code, Codex, Cursor, Grok CLI, and Antigravity.

When the git working tree has changes and the repo has a justfile with
`check-fast`, runs `just check-fast`. On failure, sends the agent back using
that tool's block format (exit 2 + stderr for Claude/Codex/Grok;
{"followup_message": ...} for Cursor; {"decision": "continue", "reason": ...}
for Antigravity). Gives up after 3 tries in one session so it never loops.

Usage: stop-check.py < hook-json  |  stop-check.py --selftest
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_TRIES = 3
JUSTFILES = ("justfile", "Justfile", ".justfile")
FILE_LINE_RE = re.compile(r"[A-Za-z0-9_./-]+\.[A-Za-z]{1,6}:[0-9]+")
ERROR_RE = re.compile(r"error|fail", re.I)
_GIT_ENV_STRIP = {
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
}


def _clean_git_env() -> dict:
    return {k: v for k, v in os.environ.items() if k not in _GIT_ENV_STRIP}


def detect_host(data: dict) -> str:
    if data.get("hookEventName") == "Stop" and any(
        k in data for k in ("terminationReason", "executionNum", "continuationActive")
    ):
        return "antigravity"
    if data.get("hook_event_name") == "stop" or "cursor_version" in data:
        return "cursor"
    return "exit2"


def allow_stop(host: str, notice: str = "") -> int:
    if host == "antigravity":
        print(json.dumps({"decision": "allow"}))
    elif host == "cursor":
        print(json.dumps({}))
    elif notice:
        print(json.dumps({"systemMessage": notice}))
    return 0


def block_stop(host: str, message: str) -> int:
    if host == "antigravity":
        print(json.dumps({"decision": "continue", "reason": message}))
        return 0
    if host == "cursor":
        print(json.dumps({"followup_message": message}))
        return 0
    sys.stderr.write(message + "\n")
    return 2


def state_file(sid: str) -> Path:
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", sid or "nosession")[:80] or "nosession"
    return Path(cache) / "ci" / "stop" / safe


def first_error_line(out: str) -> str:
    lines = [line for line in out.splitlines() if line.strip()]
    for line in lines:
        if FILE_LINE_RE.search(line):
            return line.strip()
    for line in lines:
        if ERROR_RE.search(line):
            return line.strip()
    return lines[-1].strip() if lines else "just check-fast failed"


def run_check(data: dict) -> int:
    host = detect_host(data)
    if host == "antigravity":
        reason = data.get("terminationReason")
        if reason and reason != "NO_TOOL_CALL":
            return allow_stop(host)
    if host == "cursor" and data.get("status") in ("aborted", "error"):
        return allow_stop(host)

    cwd = str(data.get("cwd") or os.getcwd())
    if not os.path.isdir(cwd):
        return allow_stop(host)

    git_env = _clean_git_env()
    top = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
        env=git_env, capture_output=True, text=True, timeout=10,
    )
    if top.returncode != 0:
        return allow_stop(host)
    root = top.stdout.strip()
    if not root or not os.path.isdir(root):
        return allow_stop(host)

    sid = str(
        data.get("session_id")
        or data.get("sessionId")
        or data.get("conversation_id")
        or data.get("conversationId")
        or "nosession"
    )
    st = state_file(sid)

    dirty = subprocess.run(
        ["git", "-C", root, "status", "--porcelain"],
        env=git_env, capture_output=True, text=True, timeout=10,
    )
    if dirty.returncode != 0 or not dirty.stdout.strip():
        st.unlink(missing_ok=True)
        return allow_stop(host)

    if not any(os.path.isfile(os.path.join(root, name)) for name in JUSTFILES):
        return allow_stop(host)

    if not shutil.which("just"):
        return allow_stop(host)

    summary = subprocess.run(
        ["just", "--summary"], cwd=root, capture_output=True, text=True, timeout=15,
    )
    if summary.returncode == 0:
        recipes = summary.stdout.split()
        if "check-fast" not in recipes:
            return allow_stop(host)
        res = subprocess.run(
            ["just", "check-fast"], cwd=root, capture_output=True, text=True, timeout=110,
        )
        if res.returncode == 0:
            st.unlink(missing_ok=True)
            return allow_stop(host)
        out = (res.stdout + ("\n" if res.stdout and res.stderr else "") + res.stderr).strip()
    else:
        out = (summary.stdout + ("\n" if summary.stdout and summary.stderr else "") + summary.stderr).strip()

    st.parent.mkdir(parents=True, exist_ok=True)
    try:
        prev = int(st.read_text().strip())
    except Exception:
        prev = 0
    tries = prev + 1
    if tries >= MAX_TRIES:
        st.unlink(missing_ok=True)
        return allow_stop(
            host,
            f"UNVERIFIED: just check-fast still fails after {MAX_TRIES} tries. Say so plainly; do not claim done.",
        )

    st.write_text(str(tries))
    first = first_error_line(out)
    tail = "\n".join(out.splitlines()[-30:])
    msg = (
        f"just check-fast failed (try {tries} of {MAX_TRIES}). First error: {first}\n"
        f"Fix it, then rerun: just check-fast\n"
        f"--- last 30 lines ---\n{tail}"
    )
    return block_stop(host, msg)


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    try:
        sys.exit(run_check(data))
    except Exception:
        sys.exit(0)


def selftest() -> None:
    if not shutil.which("just"):
        print("stop-check selftest: skipped (no just)")
        return
    script = os.path.abspath(__file__)
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        env = {**_clean_git_env(), "XDG_CACHE_HOME": str(Path(tmp) / "cache")}
        subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], env=env, check=True)
        (repo / "justfile").write_text('check-fast:\n    echo "x.ts:3: error: nope"; false\n')
        subprocess.run(["git", "-C", str(repo), "add", "-A"], env=env, check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
            env=env, check=True,
        )

        def invoke(payload):
            return subprocess.run(
                [sys.executable, script],
                input=json.dumps(payload), text=True, capture_output=True, env=env, timeout=30,
            )

        # Clean tree passes immediately
        r = invoke({"session_id": "s1", "cwd": str(repo)})
        assert r.returncode == 0 and not r.stdout.strip(), (r.returncode, r.stdout, r.stderr)

        # Dirty tree fails -> tries 1 and 2 exit 2, try 3 gives up with UNVERIFIED
        (repo / "dirty.txt").write_text("x\n")
        r1 = invoke({"session_id": "s1", "cwd": str(repo)})
        assert r1.returncode == 2 and "try 1 of 3" in r1.stderr and "x.ts:3" in r1.stderr, (r1.returncode, r1.stderr)
        r2 = invoke({"session_id": "s1", "cwd": str(repo)})
        assert r2.returncode == 2 and "try 2 of 3" in r2.stderr, (r2.returncode, r2.stderr)
        r3 = invoke({"session_id": "s1", "cwd": str(repo)})
        assert r3.returncode == 0 and "UNVERIFIED" in r3.stdout, (r3.returncode, r3.stdout)

        # Cursor format: followup_message
        rc = invoke({"hook_event_name": "stop", "conversation_id": "c1", "cwd": str(repo)})
        assert rc.returncode == 0 and "followup_message" in json.loads(rc.stdout), (rc.returncode, rc.stdout)

        # Antigravity format: decision=continue on NO_TOOL_CALL, decision=allow on USER_CANCELED
        ra = invoke({"hookEventName": "Stop", "conversationId": "a1", "terminationReason": "NO_TOOL_CALL", "cwd": str(repo)})
        out_a = json.loads(ra.stdout)
        assert ra.returncode == 0 and out_a.get("decision") == "continue" and "x.ts:3" in out_a.get("reason", ""), out_a
        ra_cancel = invoke({"hookEventName": "Stop", "conversationId": "a1", "terminationReason": "USER_CANCELED", "cwd": str(repo)})
        assert ra_cancel.returncode == 0 and json.loads(ra_cancel.stdout) == {"decision": "allow"}, ra_cancel.stdout

        # Passing check-fast allows stop
        (repo / "justfile").write_text("check-fast:\n    true\n")
        rp = invoke({"session_id": "s2", "cwd": str(repo)})
        assert rp.returncode == 0 and not rp.stdout.strip(), (rp.returncode, rp.stdout, rp.stderr)

        # Broken justfile blocks
        (repo / "justfile").write_text("broken: [\n")
        rb = invoke({"session_id": "s3", "cwd": str(repo)})
        assert rb.returncode == 2, (rb.returncode, rb.stderr)

    print("stop-check selftest: ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
