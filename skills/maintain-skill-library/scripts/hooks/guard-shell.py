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

# A secret file path, not a member access like process.env or self.key(.
SECRET = (
    r"((?<![\w$.\\-])\.env(?!\.(example|sample|template)(?![\w.-]))(\.[\w-]+)?(?![\w(\[])"  # .env, site/.env, .env.local
    r"|(?<=[\w-])(?<!process)(?<!\.meta)\.env(?=$|[\s'\"`;|&)>])"  # mcp.env, prod.env
    r"|mcp_credentials\.json|(?<![\w-])(?<!exclude=)(credentials|auth)\.json|\.netrc\b|\.npmrc\b"
    r"|[\w~*/-]\.(pem|key|p8|p12|pfx)(?=$|[\s'\"`;|&)>:,])"  # server.key, AuthKey_X.p8
    r"|id_rsa|id_ed25519|\.appstoreconnect/)"
)
SECRET_READ = re.compile(
    r"(\b(cat|less|more|head|tail|bat|strings|xxd|base64|grep|rg|awk|sed|source|cp|scp)\b|\bcurl\s.*-d\s*@)[^|;&\n]*" + SECRET,
    re.I,
)
# Interpreter code fed by a heredoc: catch direct file reads of a secret path.
SECRET_IN_CODE = re.compile(
    r"\b(open|read_text|read_bytes|readFileSync|readFile|load_dotenv|dotenv_values|Path)\s*\(\s*[^)\n]*" + SECRET,
    re.I,
)
# A shell verb named as a string inside interpreter code, e.g. subprocess.run(["cat", ".env"]).
SECRET_SUBPROCESS = re.compile(
    r"[\"'](cat|less|more|head|tail|strings|xxd|base64|grep|rg|awk|sed|source|cp|scp)\b[^\n]*" + SECRET,
    re.I,
)
HEREDOC = re.compile(r"(?<!<)<<-?(?!<)\s*(['\"]?)([A-Za-z_][\w-]*)\1")
SHELL_FED = re.compile(r"\b(sh|bash|zsh|dash|ksh|ssh|eval|source|xargs)\b")
FILE_WRITE = re.compile(r"\b(cat|tee)\b")


def _split_heredocs(cmd: str) -> tuple[str, str]:
    """Return (shell text, interpreter heredoc bodies).

    A body written to a file (cat > f <<EOF, tee f <<EOF) is data, so it is dropped.
    A body fed to a shell stays shell text. Any other body is interpreter code.
    """
    lines = cmd.split("\n")
    shell, code = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        shell.append(line)
        i += 1
        m = HEREDOC.search(line)
        if not m:
            continue
        tag, strip_tabs = m.group(2), line[m.start():m.start() + 3] == "<<-"
        body = []
        while i < len(lines) and (lines[i].lstrip("\t") if strip_tabs else lines[i]) != tag:
            body.append(lines[i])
            i += 1
        if i < len(lines):
            shell.append(lines[i])  # closing tag
            i += 1
        head = line[:m.start()].split("|")[-1].split("&&")[-1].split(";")[-1]
        tail = line[m.end():]
        if SHELL_FED.search(tail) or (SHELL_FED.search(head) and not FILE_WRITE.search(head)):
            shell.extend(body)  # piped or fed to a shell: still commands
        elif FILE_WRITE.search(head):
            continue  # written to a file or printed: data
        else:
            code.extend(body)
    return "\n".join(shell), "\n".join(code)


def secret_read(cmd: str) -> bool:
    shell, code = _split_heredocs(cmd)
    return bool(
        SECRET_READ.search(shell)
        or SECRET_IN_CODE.search(shell)
        or SECRET_IN_CODE.search(code)
        or SECRET_SUBPROCESS.search(code)
    )


DESTRUCTIVE = [
    r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r|-r\s+-f|-f\s+-r)[a-z]*\s+(~|\$HOME|/)(/?\*?\s*$|/?\s|$)",
    r"\bgit\s+push\s+.*(--force|-f\b).*\b(main|master)\b",
    r"\bgit\s+push\s+.*\s\+\S*\b(main|master)\b",  # +refspec force-push
    r"\bgit\b.*\s--no-verify\b",
    r"\bgit\s+commit\s+(-\S+\s+)*-n\b",
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
    r"\basc\s+.*--submit\b",  # asc publish appstore --submit
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
    if secret_read(cmd):
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
