#!/usr/bin/env python3
"""One shell guard for Claude, Cursor, Grok, and Codex. Fail open on parse errors.

deny: shell reads of secret files (the Read-tool hook cannot see `cat .env`).
ask:  destructive commands, deploy/publish/release commands.
Everything else is allowed.
"""
import json
import re
import shlex
import sys

SECRET = r"(\.env(?!\.(example|sample|template)(?![\w.-]))\b|mcp\.env|mcp_credentials\.json|credentials\.json|auth\.json|\.netrc\b|\.npmrc\b|\.(pem|key|p8|p12|pfx)\b|id_rsa|id_ed25519|\.appstoreconnect/)"
SECRET_READ = re.compile(
    r"\b(cat|less|more|head|tail|bat|strings|xxd|base64|grep|rg|awk|sed|source|cp|scp|curl\s+.*-d\s*@)\b[^|;&]*" + SECRET,
    re.I,
)

DESTRUCTIVE = [
    r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r|-r\s+-f|-f\s+-r)[a-z]*\s+(~|\$HOME|/)(/?\*?\s*$|/?\s|$)",
    r"\bgit\s+push\s+.*(--force|-f\b).*\b(main|master)\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bdrop\s+(database|table)\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
]

DEPLOY = [
    r"\bwrangler\s+(deploy|publish|pages\s+deploy)\b",
    r"\bvercel\b",
    r"\bfirebase\s+deploy\b",
    r"\b(npm|bun)\s+run\s+deploy\b",
    r"\bpnpm\s+(run\s+)?deploy\b",
    r"\bgh\s+release\s+create\b",
    r"\basc\.py\b.*(--yes|review-send|submit)",
]


def _command(data: dict) -> str:
    tool_input = data.get("toolInput") or data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    return str(data.get("command") or tool_input.get("command") or "")


def _emit(decision: str, reason: str = "") -> None:
    payload = {"permission": decision}
    if decision != "allow":
        payload.update(
            reason=reason,
            user_message=reason,
            agent_message=reason,
        )
    print(json.dumps(payload))


def decide(cmd: str) -> tuple[str, str]:
    # Pure literal output is documentation, not a command inside its text.
    # Keep substitutions, redirections, compound commands, and scripts guarded.
    if not any(char in cmd for char in ("$", "`", "\n", "\r")):
        try:
            tokens = list(shlex.shlex(cmd, posix=True, punctuation_chars=True))
        except ValueError:
            tokens = []
        if tokens and tokens[0] in {"echo", "printf"} and not any(
            token and all(char in "();<>|&" for char in token) for token in tokens
        ):
            return "allow", ""
    if SECRET_READ.search(cmd):
        return "deny", "Do not read secret/credential files. Check key names in code or docs instead."
    if any(re.search(p, cmd, re.I) for p in DESTRUCTIVE):
        return "ask", "Destructive command flagged. Wait for Cohen's approval."
    if any(re.search(p, cmd, re.I) for p in DEPLOY):
        return "ask", "Deploy/publish flagged. State the exact target and wait for Cohen's approval."
    return "allow", ""


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        _emit("allow")
        return
    decision, reason = decide(_command(data))
    # PascalCase events use the Claude/Codex contract. Cursor also supplies
    # model, so that field alone cannot identify its output format.
    if data.get("hook_event_name") == "PreToolUse":
        if decision == "ask":
            if "model" in data:
                decision = "deny"
        payload = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }} if decision != "allow" else {}
        print(json.dumps(payload))
        return
    _emit(decision, reason)


if __name__ == "__main__":
    main()
