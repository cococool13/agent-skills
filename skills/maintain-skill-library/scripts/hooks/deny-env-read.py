#!/usr/bin/env python3
"""Block agent reads of secret env/key files. Fail open on parse errors."""
import json
import os
import sys

DENY_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    ".env.test",
    "credentials.json",
    "service-account.json",
    "mcp.env",
    "mcp_credentials.json",
    "auth.json",
    ".netrc",
    ".npmrc",
}
ALLOW_NAMES = {".env.example", ".env.sample", ".env.template"}
DENY_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".p8")
DENY_BASENAME_CONTAINS = (".env.",)


def _tool_input(data: dict) -> dict:
    raw = data.get("toolInput") or data.get("tool_input") or {}
    return raw if isinstance(raw, dict) else {}


def _path(data: dict) -> str:
    tool_input = _tool_input(data)
    for key in ("filePath", "file_path", "path", "file", "target_file"):
        value = data.get(key) or tool_input.get(key)
        if value:
            return str(value)
    return ""


def _emit(payload: dict, structured: bool = False) -> None:
    decision = payload.get("decision") or payload.get("permission")
    if structured:
        output = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": payload.get("reason", ""),
        }} if decision != "allow" else {}
        print(json.dumps(output))
        return
    payload = {key: value for key, value in payload.items() if key in {"permission", "user_message", "agent_message"}}
    print(json.dumps(payload))


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        _emit({"permission": "allow", "decision": "allow"})
        return

    path = _path(data)
    base = os.path.basename(path)
    lower = base.lower()
    deny = lower not in ALLOW_NAMES and (
        lower in DENY_NAMES
        or lower.endswith(DENY_SUFFIXES)
        or any(x in lower for x in DENY_BASENAME_CONTAINS)
        or lower in {"id_rsa", "id_ed25519"}
    )
    if deny:
        reason = "Do not read secret/credential files. Check key names only, never values."
        _emit(
            {
                "permission": "deny",
                "decision": "deny",
                "reason": reason,
                "user_message": f"Blocked read of secret-like file: {base}",
                "agent_message": reason,
            },
            structured=data.get("hook_event_name") == "PreToolUse",
        )
    else:
        _emit({"permission": "allow", "decision": "allow"}, structured=data.get("hook_event_name") == "PreToolUse")


if __name__ == "__main__":
    main()
