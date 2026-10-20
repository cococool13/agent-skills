#!/usr/bin/python3
"""Non-blocking session budget hook (Claude Code PostToolUse + PreCompact).

Counts tool calls and compactions per session_id in a temp file. After call 300,
or after the second compaction, it adds one line of context that advises a
handoff and a fresh session. Each warning fires once. Never blocks: any error
exits 0 with no output.

Selftest: session-budget.py --selftest
"""
import json
import os
import re
import sys
import tempfile

CALL_LIMIT = 300
COMPACT_LIMIT = 2
LINE = ("Session budget: {why}. Finish the current step, write a short handoff "
        "(objective, decisions, changed files, verification, next action), and continue in a fresh session.")


def state_path(session_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:80] or "unknown"
    root = os.path.join(tempfile.gettempdir(), "claude-session-budget")
    os.makedirs(root, mode=0o700, exist_ok=True)
    return os.path.join(root, safe + ".json")


def handle(data: dict):
    path = state_path(str(data.get("session_id") or ""))
    try:
        with open(path) as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    calls = int(state.get("calls", 0))
    compactions = int(state.get("compactions", 0))
    event = data.get("hook_event_name")
    message = None
    if event == "PreCompact":
        compactions += 1
    elif event == "PostToolUse":
        calls += 1
        if calls > CALL_LIMIT and not state.get("warned_calls"):
            state["warned_calls"] = True
            message = LINE.format(why="%d tool calls" % calls)
        elif compactions >= COMPACT_LIMIT and not state.get("warned_compact"):
            state["warned_compact"] = True
            message = LINE.format(why="%d compactions" % compactions)
    state.update(calls=calls, compactions=compactions)
    with open(path, "w") as f:
        json.dump(state, f)
    if message:
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}
    return None


def selftest() -> int:
    import uuid
    sid = "selftest-" + uuid.uuid4().hex
    outputs = [handle({"session_id": sid, "hook_event_name": "PostToolUse"}) for _ in range(CALL_LIMIT + 2)]
    assert outputs[:CALL_LIMIT] == [None] * CALL_LIMIT, "warned too early"
    assert outputs[CALL_LIMIT]["hookSpecificOutput"]["additionalContext"].startswith("Session budget: 301 tool calls")
    assert outputs[CALL_LIMIT + 1] is None, "warned twice"
    sid2 = sid + "-c"
    handle({"session_id": sid2, "hook_event_name": "PreCompact"})
    assert handle({"session_id": sid2, "hook_event_name": "PostToolUse"}) is None
    handle({"session_id": sid2, "hook_event_name": "PreCompact"})
    out = handle({"session_id": sid2, "hook_event_name": "PostToolUse"})
    assert "2 compactions" in out["hookSpecificOutput"]["additionalContext"]
    for s in (sid, sid2):
        os.remove(state_path(s))
    print("session-budget selftest: ok")
    return 0


def main() -> None:
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    try:
        data = json.load(sys.stdin)
        out = handle(data) if isinstance(data, dict) else None
        if out:
            print(json.dumps(out))
    except Exception:
        pass  # non-blocking by design
    sys.exit(0)


if __name__ == "__main__":
    main()
