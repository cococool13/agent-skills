#!/usr/bin/python3
"""Block agent reads of secret env/key files. Fail closed: a parse error exits 2 (block)."""
import json
from functools import lru_cache
import os
import re
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
    ".dev.vars",
}
ALLOW_NAMES = {".env.example", ".env.sample", ".env.template"}
DENY_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".p8")
DENY_BASENAME_CONTAINS = (".env.",)

# These ordinary filenames can contain credentials. Compare full paths so a
# project's settings.json or config.toml remains readable. Never open the file.
PROTECTED_FILES = (
    "~/.claude.json", "~/.claude/settings.json", "~/.codex/config.toml",
    "~/.cursor/mcp.json", "~/.grok/config.toml",
    "~/Library/Application Support/Claude/claude_desktop_config.json",
    "~/.config/gh/hosts.yml",
    "~/.zshrc", "~/.zshenv", "~/.zprofile", "~/.config/zsh/env.zsh",
)
PROTECTED_DIRS = ("~/.config/claude-auth", "~/.config/secrets",
                  "/home/box/.config/claude-auth", "/home/box/.config/secrets",
                  "/home/box/agent-data")


@lru_cache(maxsize=1)
def protected_locations() -> tuple:
    def forms(paths):
        result = set()
        for path in paths:
            lexical = os.path.abspath(os.path.expanduser(path))
            result.update((lexical.lower(), os.path.realpath(lexical).lower()))
        return tuple(result)
    return forms(PROTECTED_FILES), forms(PROTECTED_DIRS)


def matches_protected(value: str) -> bool:
    files, directories = protected_locations()
    return (any(value == target or value.startswith(target + ".") or value == target + "~" for target in files)
            or any(value == target or value.startswith(target + os.sep) for target in directories))


def protected_path(path: str, cwd: str = "") -> bool:
    def canonical(value: str) -> str:
        value = os.path.expanduser(value)
        if not os.path.isabs(value):
            value = os.path.join(cwd or os.getcwd(), value)
        return os.path.realpath(value).lower()

    # Check both lexical path and symlink target, including backup siblings.
    candidate = canonical(path)
    lexical = os.path.abspath(os.path.join(cwd or os.getcwd(), os.path.expanduser(path))).lower()
    return matches_protected(candidate) or matches_protected(lexical)


def secret_name(path: str) -> bool:
    lower = os.path.basename(path).lower()
    # Inspect backup preimages too; an extension such as .old does not remove
    # the sensitivity of auth.json, .npmrc or a private key.
    lower = re.sub(r"(?:\.(?:bak\w*|backup\w*|old|orig|save)(?:[.-].*)?|~)$", "", lower)
    return lower not in ALLOW_NAMES and (
        lower in DENY_NAMES
        or lower.endswith(DENY_SUFFIXES)
        or any(x in lower for x in DENY_BASENAME_CONTAINS)
        or lower in {"id_rsa", "id_ed25519"}
    )


def unsafe_search_scope(path: str, cwd: str) -> bool:
    """Reject recursive searches encompassing known protected locations."""
    scope = os.path.realpath(os.path.join(cwd, os.path.expanduser(path or '.')))
    scope_key = scope.lower()
    files, directories = protected_locations()
    if any(target == scope_key or target.startswith(scope_key.rstrip(os.sep) + os.sep)
           for target in files + directories):
        return True
    # A project directory can contain env files too. Inspect names/links only,
    # never contents. Bound work and refuse uncertain or symlinked subtrees.
    if not os.path.exists(scope) or os.path.isfile(scope):
        return False
    count = 0
    def unreadable(error):
        raise error
    try:
        for directory, dirs, files in os.walk(scope, onerror=unreadable, followlinks=False):
            for name in dirs + files:
                count += 1
                if count > 20000:
                    return True
                child = os.path.join(directory, name)
                if secret_name(child) or matches_protected(child.lower()) or os.path.islink(child):
                    return True
    except OSError:
        return True
    return False


def _tool_input(data: dict) -> dict:
    raw = data.get("toolInput", data.get("tool_input", {}))
    if not isinstance(raw, dict):
        raise ValueError("tool input is not an object")
    return raw


def _path(data: dict) -> str:
    tool_input = _tool_input(data)
    for key in ("filePath", "file_path", "path", "file", "target_file"):
        value = data.get(key) or tool_input.get(key)
        if value:
            if not isinstance(value, str):
                raise ValueError("path is not a string")
            return value
    return ""


def _emit(payload: dict, structured: bool = False) -> None:
    decision = payload.get("decision") or payload.get("permission")
    if structured:
        output = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": payload.get("reason", ""),
        }} if decision != "allow" else None
        if output:
            print(json.dumps(output))  # allow prints nothing: native permissions apply
        return
    payload = {key: value for key, value in payload.items() if key in {"permission", "user_message", "agent_message"}}
    print(json.dumps(payload))


def main() -> None:
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError("hook input is not an object")
    except Exception as exc:  # fail closed
        sys.stderr.write("deny-env-read: blocked, hook error: %s\n" % exc.__class__.__name__)
        sys.exit(2)

    structured = data.get("hook_event_name") == "PreToolUse"
    if data.get("toolInputTruncated") is True or data.get("tool_input_truncated") is True:
        reason = "Tool input was truncated, so the guard cannot see the whole path."
        _emit(
            {
                "permission": "deny",
                "decision": "deny",
                "reason": reason,
                "user_message": reason,
                "agent_message": reason,
            },
            structured=structured,
        )
        return

    tool = str(data.get("tool_name") or data.get("toolName") or "").lower()
    try:
        path = _path(data)
        if not path and tool not in {"grep", "search"}:
            raise ValueError("read path missing")
        cwd = data.get("cwd", os.getcwd())
        if not isinstance(cwd, str):
            raise ValueError("cwd is not a string")
        cwd = cwd or os.getcwd()
    except ValueError:
        sys.stderr.write("deny-env-read: blocked, invalid read input\n")
        sys.exit(2)
    base = os.path.basename(path)
    resolved = os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))
    deny = protected_path(path, cwd) or secret_name(path) or secret_name(resolved)
    if tool in {"grep", "search"}:
        deny = deny or unsafe_search_scope(path, cwd)
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
            structured=structured,
        )
    else:
        _emit({"permission": "allow", "decision": "allow"}, structured=structured)


if __name__ == "__main__":
    main()
