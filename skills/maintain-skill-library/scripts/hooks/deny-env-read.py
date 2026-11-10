#!/usr/bin/python3
"""Block agent reads of secret env/key files. Fail closed: a parse error exits 2 (block)."""
import fnmatch
import json
from functools import lru_cache
import os
import re
import subprocess
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
ALLOW_SUFFIXES = (".example", ".sample", ".template")  # appstoreconnect.env.example
# Public halves and CA bundles carry no secret: id_ed25519.pub, test-pubkey.pem, cacert.pem.
PUBLIC_NAME = re.compile(
    r"(\.pub$|(^|[-_.])pub(lic)?[-_.]?key\.pem$|^(cacert|ca-bundle|ca-certificates)\.(pem|crt)$)")
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
    if lower in ALLOW_NAMES or lower.endswith(ALLOW_SUFFIXES):
        return False
    if PUBLIC_NAME.search(lower) and "priv" not in lower:
        return False
    return (
        lower in DENY_NAMES
        or lower.endswith(DENY_SUFFIXES)
        or lower.endswith(".env")  # prod.env, as the shell guard already treats it
        or any(x in lower for x in DENY_BASENAME_CONTAINS)
        or lower in {"id_rsa", "id_ed25519"}
    )


SCOPE_WALK_LIMIT = 50000
SCOPE_GLOB_WALK_LIMIT = 300000
SCOPE_LIST_LIMIT = 200000
SCOPE_REASON = ("This search would read a credential-like file in its scope. Search a subdirectory, "
                "or limit it to a file type (rg -g '*.ts'). Do not search credential files.")
IGNORE_OVERRIDES = (".ignore", ".rgignore")  # ripgrep ranks these above .gitignore


def _brace_expand(glob: str) -> list:
    match = re.search(r"\{([^{}]*)\}", glob)
    if not match:
        return [glob]
    out = []
    for option in match.group(1).split(","):
        out += _brace_expand(glob[:match.start()] + option + glob[match.end():])
    return out


def _glob_hits(relative: str, globs) -> bool:
    """True when an include glob could select this path. Errs towards True.

    Only the glob's last component is used, and it is tried against every
    component of the path, because a glob that names a directory selects
    everything below it.
    """
    parts = [part for part in relative.lower().split(os.sep) if part]
    for glob in globs:
        for candidate in _brace_expand(glob.replace("\\", "")):
            base = candidate.rstrip("/").rsplit("/", 1)[-1].lower().replace("**", "*")
            if not base or base == "*" or "{" in base or "}" in base:
                return True
            if any(fnmatch.fnmatchcase(part, base) for part in parts):
                return True
    return False


def _git(scope: str, *args):
    result = subprocess.run(["git", "-C", scope, *args], capture_output=True, timeout=5)
    return result.returncode, result.stdout


def _git_scope_unsafe(scope: str, depth: int = 0):
    """Check the files a gitignore-respecting search reads. None when git cannot say."""
    if depth > 3:
        return True
    try:
        code, _ = _git(scope, "check-ignore", "-q", ".")
        if code != 1:
            return None  # the scope itself is ignored (so searched in full) or is not in a repository
        code, top = _git(scope, "rev-parse", "--show-toplevel")
        code_listed, listed = _git(scope, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        code_ignored, ignored = _git(scope, "ls-files", "-z", "--others", "--ignored",
                                     "--exclude-standard", "--directory")
    except (OSError, subprocess.SubprocessError):
        return None
    if code or code_listed or code_ignored:
        return None
    toplevel = os.path.realpath(os.fsdecode(top).strip())
    names = [os.fsdecode(name) for name in listed.split(b"\0") if name]
    skipped = [os.fsdecode(name) for name in ignored.split(b"\0") if name]
    if len(names) + len(skipped) > SCOPE_LIST_LIMIT:
        return True
    # ripgrep stops trusting git where its own ignore files or a second .git appear:
    # .ignore/.rgignore can re-include an ignored file, and a .git directory ends the
    # parent repository's rules. Look in every directory the search can enter, and above.
    directories = {""}
    for name in names + skipped:
        parent = os.path.dirname(name.rstrip("/"))
        while parent and parent not in directories:
            directories.add(parent)
            parent = os.path.dirname(parent)
    for relative in directories:
        directory = os.path.join(scope, relative) if relative else scope
        if any(os.path.lexists(os.path.join(directory, marker)) for marker in IGNORE_OVERRIDES):
            return None
        if os.path.lexists(os.path.join(directory, ".git")) and os.path.realpath(directory) != toplevel:
            return None
    above = os.path.dirname(scope)
    while True:
        if any(os.path.lexists(os.path.join(above, marker)) for marker in IGNORE_OVERRIDES):
            return None
        if above == os.path.dirname(above):
            break
        above = os.path.dirname(above)
    for name in names:
        child = os.path.join(scope, name.rstrip("/"))
        if secret_name(child) or matches_protected(child.lower()):
            return True
        if os.path.islink(child):
            continue  # the search does not follow it
        if name.endswith("/") or os.path.isdir(child):  # nested repository or submodule
            nested = _git_scope_unsafe(child, depth + 1)
            if nested is None:
                nested = _walk_unsafe(child, False)
            if nested:
                return True
    return False


def _walk_unsafe(scope: str, follow_links: bool, include=None) -> bool:
    """Inspect every name under scope, never contents. Refuse when the walk is uncertain.

    With include globs, only credential-like files those globs could select count.
    """
    count, limit = 0, SCOPE_GLOB_WALK_LIMIT if include else SCOPE_WALK_LIMIT
    def unreadable(error):
        raise error
    try:
        for directory, dirs, files in os.walk(scope, onerror=unreadable, followlinks=False):
            for name in dirs + files:
                count += 1
                if count > limit:
                    return True
                child = os.path.join(directory, name)
                if follow_links and os.path.islink(child):
                    return True  # the search would leave the inspected tree
                if secret_name(child) or matches_protected(child.lower()):
                    if include is None or _glob_hits(os.path.relpath(child, scope), include):
                        return True
    except OSError:
        return True
    return False


def unsafe_search_scope(path: str, cwd: str, respect_ignore: bool = False,
                        follow_links: bool = False, globs=()) -> bool:
    """Reject recursive searches that would read a credential-like file.

    respect_ignore: the tool skips gitignored files (ripgrep and the Grep tools).
    follow_links: the tool follows symlinks. globs: its include and exclude globs.
    Names and links are inspected, never contents.
    """
    scope = os.path.realpath(os.path.join(cwd, os.path.expanduser(path or '.')))
    scope_key = scope.lower()
    files, directories = protected_locations()
    if any(target == scope_key or target.startswith(scope_key.rstrip(os.sep) + os.sep)
           for target in files + directories):
        return True
    if not os.path.exists(scope) or os.path.isfile(scope):
        return False
    include = [glob for glob in globs if glob and not glob.startswith("!")]
    if include and not follow_links:
        # An include glob overrides gitignore: every file it can select is read.
        return _walk_unsafe(scope, False, include)
    if respect_ignore and not follow_links:
        verdict = _git_scope_unsafe(scope)
        if verdict is not None:
            return verdict
    return _walk_unsafe(scope, follow_links)


SEARCH_TOOLS = {"grep", "search", "grep_search"}  # ripgrep-backed in Claude and Grok


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
        if not path and tool not in SEARCH_TOOLS:
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
    reason = "Do not read secret/credential files. Check key names only, never values."
    if not deny and tool in SEARCH_TOOLS:
        tool_input = _tool_input(data)
        globs = [str(tool_input[key]) for key in ("glob", "include") if tool_input.get(key)]
        if unsafe_search_scope(path, cwd, respect_ignore=True, globs=globs):
            deny, reason = True, SCOPE_REASON
    if deny:
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
