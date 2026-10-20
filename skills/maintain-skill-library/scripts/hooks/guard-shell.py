#!/usr/bin/python3
"""One shell guard for Claude, Cursor, Grok, and Codex. Fail closed.

deny: secret reads (files, env dumps, Keychain, gh token), force-push, live Stripe,
      rm -rf outside ~/Projects/<repo>, temp dirs, or build dirs.
ask:  deploys, releases, publishes, notarization submits, merges, and the
      destructive git commands in Cohen's authorization list.
Everything else: Claude/Codex get no output (native permissions apply);
Cursor gets {"permission": "allow"} because its contract needs JSON.
A parse or runtime error exits 2, which every client treats as a block.
"""
import json
import os
import re
import shlex
import sys

HOME = os.path.expanduser("~")

# A secret file path, not a member access like process.env or self.key(.
SECRET = (
    r"((?<![\w$.\\-])\.env(?!\.(example|sample|template)(?![\w.-]))(\.[\w-]+)?(?![\w(\[])"  # .env, site/.env, .env.local
    r"|(?<=[\w-])(?<!process)(?<!\.meta)\.env(?=$|[\s'\"`;|&)>])"  # mcp.env, prod.env
    r"|mcp_credentials\.json|(?<![\w-])(?<!exclude=)(credentials|auth)\.json|\.netrc\b|\.npmrc\b|\.dev\.vars(?![\w.])"
    r"|[\w~*/-]\.(pem|key|p8|p12|pfx)(?=$|[\s'\"`;|&)>:,])"  # server.key, AuthKey_X.p8
    r"|id_rsa|id_ed25519|\.appstoreconnect/)"
)
SECRET_READ = re.compile(
    r"(\b(cat|less|more|head|tail|bat|strings|xxd|od|hexdump|base64|grep|rg|awk|sed|source|cp|scp|rsync|nl|tac)\b"
    r"|(?:^|[;&|(\n])\s*\.\s"  # `. file` sources it
    r"|\bcurl\s.*(-d|--data(-binary|-raw|-urlencode)?|-F|--form|-T|--upload-file)[\s=]*\S*@?)[^|;&\n]*" + SECRET,
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

# Start of a simple command: line start, a separator, or a substitution.
CMD = r"(?:^|[;&|(\n]|\$\(|`)\s*(?:sudo\s+|command\s+|exec\s+|time\s+)*"
END = r"\s*(?=$|[;&|)>\n`])"

SECRET_COMMANDS = [
    CMD + r"(?:/usr/bin/)?printenv\b",  # prints values, with or without a name
    CMD + r"(?:/usr/bin/)?env(?:\s+-[-\w]+)*" + END,  # bare env dumps everything
    CMD + r"(?:export|declare|typeset)\s+-[a-z]*p[a-z]*" + END,
    CMD + r"(?:export|declare\s+-x|typeset\s+-x)" + END,
    CMD + r"set" + END,
    r"\blaunchctl\s+getenv\b",
    r"\bsecurity\s+(find-generic-password|find-internet-password|find-certificate\s+.*-p|export|dump-keychain|dump-trust-settings)\b",
    r"\bgh\s+auth\s+token\b",
    r"\bgh\s+auth\s+status\b.*(--show-token|\s-t\b)",
    r"\bgit\s+credential(-osxkeychain)?\s+(fill|get)\b",
    r"\bsk_live_[0-9A-Za-z]",
    r"\bstripe\b[^|;&\n]*\s--live\b",
]

FORCE_PUSH = [
    r"\bgit\s+push\b[^|;&\n]*\s(--force(-with-lease)?(=\S*)?|-[a-zA-Z]*f[a-zA-Z]*)(?=\s|$)",
    r"\bgit\s+push\b[^|;&\n]*\s\+\S+",  # +refspec force-push
]

ASK = [
    # Cohen's authorization list: destructive git.
    r"\bgit\b.*\s--no-verify\b",
    r"\bgit\s+commit\s+(-\S+\s+)*-n\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bdrop\s+(database|table)\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    # Deploys, releases, publishes, submits, merges.
    r"\bwrangler\s+(deploy|publish|pages\s+deploy|versions\s+deploy|secret\s+put)\b",
    r"\bvercel\b",
    r"\bnetlify\s+deploy\b",
    r"\bfirebase\s+deploy\b",
    r"\b(npm|bun|yarn)\s+run\s+(deploy|release|publish)\b",
    r"\bpnpm\s+(run\s+)?(deploy|release)\b",
    r"\b(npm|pnpm|yarn|bun|cargo)\s+publish\b",
    r"\btwine\s+upload\b",
    r"\bgh\s+release\s+create\b",
    r"\bgh\s+pr\s+merge\b",
    r"\bgh\s+repo\s+(delete|archive|edit\b.*--visibility)",
    r"\bxcrun\s+(notarytool\s+submit|altool\s+--upload)",
    r"\basc\.py\b.*(--yes|review-send|submit)",
    r"\basc\s+.*--submit\b",  # asc publish appstore --submit
    r"\bfastlane\s+(deliver|pilot|upload_to)",
    # The Stripe CLI here defaults to LIVE mode: ask unless the command is test-mode or local-only.
    CMD + r"stripe\s(?![^;&|\n]*(--test\b|sk_test_|\blisten\b|\btrigger\b|--version\b|\bconfig\b|--help\b))",
]

BUILD_DIRS = {
    "node_modules", "dist", "build", ".build", "out", ".next", ".nuxt", ".svelte-kit", ".astro",
    ".turbo", ".cache", "coverage", "target", ".wrangler", ".venv", "venv", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "DerivedData", ".swiftpm", ".expo",
}
TEMP_ROOTS = ("/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/")
RM = re.compile(r"(?:^|[;&|(\n]|\$\()\s*(?:sudo\s+)?(?:/bin/)?rm\s+([^;&|\n)]*)")


def _split_heredocs(cmd: str):
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


def secret_read(shell: str, code: str) -> bool:
    return bool(
        SECRET_READ.search(shell)
        or SECRET_IN_CODE.search(shell)
        or SECRET_IN_CODE.search(code)
        or SECRET_SUBPROCESS.search(code)
    )


def _rm_target_ok(target: str, cwd: str) -> str:
    """Return 'ok', 'deny' or 'ask' for one rm -rf target."""
    t = target
    if t.startswith("~"):
        t = HOME + t[1:]
    t = t.replace("${HOME}", HOME).replace("$HOME", HOME)
    if "$" in t or "`" in t:
        return "ask"  # cannot resolve a variable target
    if not t.startswith("/"):
        if not cwd:
            return "ok" if not t.startswith("..") else "ask"
        t = os.path.join(cwd, t)
    path = os.path.normpath(t)
    parts = path.split("/")
    if path in ("/", HOME) or path == HOME + "/Projects" or path.rstrip("*/") in ("", HOME, HOME + "/Projects"):
        return "deny"
    if (path + "/").startswith(TEMP_ROOTS):
        return "ok"
    if any(p in BUILD_DIRS for p in parts) and path.startswith(HOME + "/"):
        return "ok"
    if path.startswith(HOME + "/Projects/"):
        rest = path[len(HOME + "/Projects/"):]
        if rest and not rest.startswith("*"):
            return "ok"
    return "deny"


def rm_decision(shell: str, cwd: str) -> str:
    worst = "ok"
    for m in RM.finditer(shell):
        try:
            tokens = shlex.split(m.group(1))
        except ValueError:
            tokens = m.group(1).split()
        flags = "".join(t.lstrip("-") for t in tokens if t.startswith("-") and not t.startswith("--"))
        longs = {t for t in tokens if t.startswith("--")}
        recursive = "r" in flags or "R" in flags or "--recursive" in longs
        force = "f" in flags or "--force" in longs
        if not (recursive and force):
            continue
        targets = [t for t in tokens if not t.startswith("-")] or ["?"]
        for target in targets:
            verdict = _rm_target_ok(target, cwd)
            if verdict == "deny":
                return "deny"
            if verdict == "ask":
                worst = "ask"
    return worst


def _command(data: dict) -> str:
    tool_input = data.get("toolInput") or data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    return str(data.get("command") or tool_input.get("command") or "")


def decide(cmd: str, cwd: str = ""):
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
    shell, code = _split_heredocs(cmd)
    if secret_read(shell, code):
        return "deny", "Do not read secret/credential files. Check key names in code or docs instead."
    if any(re.search(p, shell, re.I) for p in SECRET_COMMANDS):
        return "deny", "Do not print environment values, Keychain items, tokens, or use live Stripe."
    if any(re.search(p, shell) for p in FORCE_PUSH):
        return "deny", "Force-push is blocked. Push a new branch or ask Cohen."
    rm = rm_decision(shell, cwd)
    if rm == "deny":
        return "deny", "rm -rf is allowed only inside ~/Projects/<repo>, temp dirs, or build dirs."
    if rm == "ask":
        return "ask", "rm -rf with an unresolved target. Wait for Cohen's approval."
    if any(re.search(p, shell, re.I) for p in ASK):
        return "ask", "Deploy, release, publish, submit, merge, or destructive git. State the exact target and wait for Cohen's approval."
    return "allow", ""


def main() -> None:
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError("hook input is not an object")
        decision, reason = decide(_command(data), str(data.get("cwd") or ""))
    except Exception as exc:  # fail closed
        sys.stderr.write("guard-shell: blocked, hook error: %s\n" % exc.__class__.__name__)
        sys.exit(2)
    # PascalCase events use the Claude/Codex contract. Codex also sends model
    # and rejects "ask", so it gets "deny" with the same reason.
    if data.get("hook_event_name") == "PreToolUse":
        if decision == "allow":
            return  # no output: native permissions apply
        if decision == "ask" and "model" in data:
            decision = "deny"
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }}))
        return
    payload = {"permission": decision}
    if decision != "allow":
        payload.update(user_message=reason, agent_message=reason)
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
