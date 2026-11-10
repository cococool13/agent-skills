#!/usr/bin/python3
"""One shell guard for Claude, Cursor, Grok, and Codex. Fail closed.

The verdict comes from every simple command in the text (after ;, &&, |, $( ),
backticks, bash -c, eval), not from the command prefix.
deny: any mention of a secret path (except ls/test/stat/wc -c/shasum/jq keys/grep -c/
      chmod/cp -p/mv of it), env dumps, Keychain, gh token, live Stripe, force-push,
      rm -r / find -delete / xargs rm outside $PWD, ~/Projects/<repo> build dirs, or temp dirs.
ask:  deploys, releases, publishes, App Store uploads, merges, remote curl/gh api writes,
      git --no-verify / -n / reset --hard / push --delete / --force-with-lease off main,
      deploy-named scripts (by file name; check/test/notes/dry-run names are exempt).
Recursive search: ripgrep reads what git does not ignore and follows no symlinks, so its scope
is judged from git's file list; grep -r, ag, ack and rg --no-ignore/-u/-L get a full name walk.
A project's own .claude/settings.json is an ordinary file; the user-level one is a secret.
Everything else: Claude/Codex get no output (native permissions apply);
Cursor gets {"permission": "allow"} because its contract needs JSON.
A parse or runtime error exits 2, which every client treats as a block.
"""
import hashlib
from functools import lru_cache
import json
import os
import re
import runpy
import sys
import time

HOME = os.path.expanduser("~")
PROJECTS = HOME + "/Projects"

# A secret file path, not a member access like process.env or self.key(.
_NOT_EXAMPLE = r"(?!\.(example|sample|template)(?![\w.-]))"
SECRET = (
    r"((?<![\w$.\\-])\.env" + _NOT_EXAMPLE + r"(\.[\w-]+)*(?![\w(\[])"  # .env, site/.env, .env.local
    r"|(?<=[\w-])(?<!process)(?<!\.meta)\.env" + _NOT_EXAMPLE + r"(\.[\w-]+)*(?=$|[\s'\"`;|&)>:,])"  # mcp.env(.bak)
    r"|mcp_credentials|(?<![\w-])(?<!exclude=)(credentials|auth)\.json|\.netrc\b|\.npmrc\b"
    r"|\.dev\.vars" + _NOT_EXAMPLE + r"(?![\w])"
    r"|hosts\.yml\b|AuthKey_|\.claude\.json|\.claude/settings\.json|\.grok/config\.toml|\.codex/config\.toml|\.cursor/mcp\.json|settings\.json\.bak"
    r"|\.config/claude-auth/|\.config/secrets/|/home/box/agent-data/"
    r"|\.zsh(rc|env|profile)\b|\.config/zsh/env\.zsh"
    r"|[\w~*/-]\.(pem|p8|p12|pfx)(?=$|[\s'\"`;|&)>:,])"  # server.pem, AuthKey_X.p8
    r"|[\w~*/-]\.key(?=$|[\s'\"`|&>:])"  # server.key, not obj.key) or obj.key,
    r"|id_rsa|id_ed25519|\.appstoreconnect/)"
)
SECRET_RE = re.compile(SECRET, re.I)
# Public halves and CA bundles carry no secret: id_ed25519.pub, test-pubkey.pem, cacert.pem.
PUBLIC_TOKEN = re.compile(
    r"(\.pub$|(^|[-_./])pub(lic)?[-_.]?key\.pem$|(^|/)(cacert|ca-bundle|ca-certificates)\.pem$)", re.I)
PROJECT_SETTINGS = re.compile(r"\.claude/settings\.json$", re.I)
TOKEN_EDGE = " \t\r\n'\"`()=,;<>|&"
# A token the shell may rewrite (brace, glob, variable, xargs placeholder) is never exempt.
TOKEN_META = set("{}*?[]$\\%!^~")
# A relative path is trusted only in one plain command from this list (see _simple_command).
SIMPLE_READERS = {"cat", "head", "tail", "less", "ls", "wc", "diff", "jq", "sed", "grep", "rg",
                  "code", "open", "touch", "mkdir", "git"}
_COMMAND = ""  # the whole text under judgement, for _simple_command

HEREDOC = re.compile(r"(?<!<)<<-?(?!<)\s*(['\"]?)([A-Za-z_][\w-]*)\1")
SHELL_FED = re.compile(r"\b(sh|bash|zsh|dash|ksh|ssh|eval|source|xargs)\b")
FILE_WRITE = re.compile(r"\b(cat|tee)\b")

# Start of a simple command: line start, a separator, a substitution, or a -c string.
CMD = r"(?:^|[;&|(\n]|\$\(|`|\s-c\s+['\"]|\beval\s+['\"]?)\s*(?:sudo\s+|command\s+|exec\s+|time\s+)*"
END = r"\s*(?=$|[;&|)>\n`'\"])"

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

# Whole-text asks for tools the token checks below do not model.
ASK = [
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bfirebase\s+(deploy|hosting)",
    # Remote code run straight from the network.
    r"\b(curl|wget)\b[^\n;&]*\|\s*(sudo\s+)?(sh|bash|zsh|dash|python3?)\b",
    r"\b(sh|bash|zsh|dash)\b[^\n;&|]*(<\(|\$\(|`)\s*(curl|wget)\b",
    r"\bcargo\s+publish\b",
    r"\btwine\s+upload\b",
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
TMP_MARK = "/private/tmp/__tmpdir__"  # stands in for $TMPDIR
UNSAFE_CWD_ROOTS = {"Library", "Documents", "Desktop", "Downloads", "Pictures", "Movies", "Music",
                    "Projects", ".ssh", ".gnupg", ".aws"}

SCRATCH_ROOT = HOME + "/Library/Application Support/Claude/scratch-workspaces/"  # the app's per-session folders

SCRIPT_WORD = re.compile(r"(?<![a-z])(deploy|release|publish|ship)(?![a-z])", re.I)
# A script named for checking a deploy is not a deploy: check-dmg-release.sh, deploy.test.js, release-notes.
SAFE_SCRIPT_WORD = re.compile(
    r"(\.(test|spec)\.\w+$|^(tests?|check|lint|verify)[-_:.]"
    r"|(deploy|release|publish|ship)[-_:]?(notes|status|plan|check|dry-?run)(?![a-z]))", re.I)
JOINED_SCRIPT_WORD = re.compile(r"(?<![a-z])(and|then)(?![a-z])", re.I)  # check-then-publish.sh does publish
SCRIPT_EXT = re.compile(r"\.(sh|bash|zsh|py|js|mjs|cjs|ts|rb|pl)$", re.I)
DROP_SQL = re.compile(r"\bdrop\s+(database|table)\b", re.I)
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
INTERPRETERS = SHELLS | {"node", "python", "python3", "ruby", "perl", "bun", "deno", "tsx", "ts-node", "php"}
RUNNERS = SHELLS | {"eval", "source", ".", "parallel", "read"}
PATTERN_TOOLS = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "sed", "awk", "gawk", "jq", "yq"}
# Commands whose arguments are text to store, show or search for, not SQL to run.
TEXT_ONLY = PATTERN_TOOLS | {"git", "gh", "echo", "printf", "ls", "cat", "open"}
PATTERN_VALUE_FLAGS = {
    "-A", "-B", "-C", "-m", "-g", "--glob", "--iglob", "-t", "--type", "-T", "--type-not", "--max-count",
    "--arg", "--argjson", "-d", "--include", "--exclude", "--exclude-dir", "-M", "--max-columns",
    "--context", "--before-context", "--after-context",
}
PREFIX = {"sudo", "doas", "command", "builtin", "exec", "time", "nohup", "nice", "caffeinate", "stdbuf",
          "timeout", "gtimeout", "unbuffer", "if", "then", "else", "elif", "do", "while", "until", "!", "{", "}"}
OPS = ["&&", "||", ";;", "|&", "&>>", "&>", ">>", "<<<", "<<", ">&", "<&", ">|",
       ";", "&", "|", "(", ")", ">", "<", "\n"]
REDIRS = {"&>>", "&>", ">>", "<<<", "<<", ">&", "<&", ">|", ">", "<"}
LEVEL = {"allow": 0, "ask": 1, "deny": 2}

R_SECRET = "Do not read secret/credential files. Check key names in code or docs instead."
R_ENV = "Do not print environment values, Keychain items, tokens, or use live Stripe."
R_FORCE = "Force-push is blocked. On a branch other than main, --force-with-lease can be approved by Cohen; otherwise push a new branch."
R_RM = "Recursive delete is allowed only inside the working directory, ~/Projects/<repo> build dirs, or temp dirs."
R_RM_ASK = "Recursive delete with an unresolved target. Wait for Cohen's approval."
R_ASK = "Deploy, release, publish, submit, merge, remote write, or destructive git. State the exact target and wait for Cohen's approval."


class Verdict:
    def __init__(self):
        self.decision, self.reason = "allow", ""
        self.names = set()  # every command name seen, for whole-text rules

    def add(self, decision, reason):
        if LEVEL[decision] > LEVEL[self.decision]:
            self.decision, self.reason = decision, reason

    def merge(self, other):
        self.add(other.decision, other.reason)
        self.names |= other.names


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


def _extract_subst(text: str):
    """Replace $( ), <( ), >( ) and backticks with $SUBST; return (text, inner commands)."""
    out, inner = [], []
    i, n, sq, dq = 0, len(text), False, False
    while i < n:
        c = text[i]
        if sq:
            sq = c != "'"
            out.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(text[i:i + 2])
            i += 2
            continue
        if c == "'" and not dq:
            sq = True
        elif c == '"':
            dq = not dq
        elif c == "`":
            j = text.find("`", i + 1)
            j = n if j < 0 else j
            inner.append(text[i + 1:j])
            out.append("$SUBST")
            i = j + 1
            continue
        elif text.startswith(("$(", "<(", ">("), i):
            depth, j = 1, i + 2
            while j < n and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            inner.append(text[i + 2:j - 1] if depth == 0 else text[i + 2:])
            out.append("$SUBST")
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out), inner


def _lex(text: str):
    """Shell words and operators. Quotes are removed; comments are dropped."""
    toks, buf, i, n = [], None, 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r":
            if buf is not None:
                toks.append(("w", buf))
                buf = None
            i += 1
            continue
        if c == "#" and buf is None:
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "\\":
            if text[i + 1:i + 2] != "\n":
                buf = (buf or "") + text[i + 1:i + 2]
            i += 2
            continue
        if c == "'" or text.startswith("$'", i):
            start = i + (2 if c == "$" else 1)
            j = text.find("'", start)
            j = n if j < 0 else j
            buf = (buf or "") + text[start:j]
            i = j + 1
            continue
        if c == '"':
            j, s = i + 1, []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n and text[j + 1] in '"\\$`\n':
                    s.append(text[j + 1])
                    j += 2
                    continue
                s.append(text[j])
                j += 1
            buf = (buf or "") + "".join(s)
            i = j + 1
            continue
        op = next((o for o in OPS if text.startswith(o, i)), None)
        if op:
            if op in REDIRS and buf is not None and buf.isdigit():
                buf = None  # 2>file: the fd is not an argument
            if buf is not None:
                toks.append(("w", buf))
                buf = None
            toks.append(("op", op))
            i += len(op)
            continue
        buf = (buf or "") + c
        i += 1
    if buf is not None:
        toks.append(("w", buf))
    return toks


def _segments(toks):
    """Group tokens into simple commands: {argv, redirs, pipe}."""
    segs, pipe, pending = [], 0, None
    cur = {"argv": [], "redirs": [], "pipe": 0}
    for kind, v in toks:
        if kind == "w":
            if pending:
                cur["redirs"].append((pending, v))
                pending = None
            else:
                cur["argv"].append(v)
            continue
        if v in REDIRS:
            pending = v
            continue
        if cur["argv"] or cur["redirs"]:
            segs.append(cur)
        if v not in ("|", "|&"):
            pipe += 1
        cur = {"argv": [], "redirs": [], "pipe": pipe}
    if cur["argv"] or cur["redirs"]:
        segs.append(cur)
    return segs


def _name(token: str) -> str:
    b = os.path.basename(token.rstrip("/")) or token
    b = re.sub(r"^\$\{?([A-Za-z_]\w*)\}?$", r"\1", b)  # $WRANGLER, ${GIT}
    if not b.startswith("@"):
        b = b.split("@", 1)[0]  # wrangler@4
    return b.lower()


def _normalize(argv):
    """Strip VAR=x, sudo/time/env/xargs/npx and friends. Return (argv, via_xargs)."""
    a, xargs = list(argv), False
    while a:
        t, b = a[0], _name(a[0])
        if re.match(r"^[A-Za-z_]\w*=", t):
            a.pop(0)
            continue
        if b in PREFIX:
            a.pop(0)
            while a and a[0].startswith("-") and a[0] != "-":
                f = a.pop(0)
                if a and ((b in ("sudo", "doas") and f in ("-u", "-g", "-C", "-h", "-p", "-U", "-r", "-t"))
                          or (b == "nice" and f == "-n")
                          or (b in ("timeout", "gtimeout") and f in ("-s", "-k", "--signal", "--kill-after"))):
                    a.pop(0)
            if b in ("timeout", "gtimeout") and a:
                a.pop(0)  # duration
            continue
        if b == "env" and len(a) > 1:
            a.pop(0)
            while a and (a[0].startswith("-") or re.match(r"^[A-Za-z_]\w*=", a[0])):
                f = a.pop(0)
                if f in ("-u", "-C", "-S", "-P") and a:
                    a.pop(0)
            continue
        if b == "xargs":
            xargs = True
            a.pop(0)
            while a and a[0].startswith("-"):
                f = a.pop(0)
                if f in ("-I", "-J", "-n", "-P", "-L", "-s", "-d", "-E", "-a", "-R", "-S") and a:
                    a.pop(0)
            continue
        if b in ("npx", "bunx", "pnpx") or (b in ("pnpm", "yarn", "npm", "bun") and len(a) > 1 and a[1] in ("dlx", "exec", "x")):
            a = a[1:] if b in ("npx", "bunx", "pnpx") else a[2:]
            while a and a[0].startswith("-"):
                f = a.pop(0)
                if f in ("-p", "--package", "-c", "--call") and a:
                    a.pop(0)
            continue
        break
    return a, xargs


# ---------- paths and deletes ----------

def _expand(t: str, cwd):
    """Absolute normalized path; a relative path when cwd is unknown; None when unresolved."""
    if t == "~" or t.startswith("~/"):
        t = HOME + t[1:]
    elif t.startswith("~"):
        return "/"  # ~user: someone else's home
    t = t.replace("${HOME}", HOME).replace("$HOME", HOME)
    t = t.replace("${TMPDIR}", TMP_MARK).replace("$TMPDIR", TMP_MARK)
    if cwd:
        t = t.replace("${PWD}", cwd).replace("$PWD", cwd)
    if "$" in t or "`" in t:
        return None
    if not t.startswith("/"):
        if not cwd:
            return t
        t = os.path.join(cwd, t)
    return "/" + os.path.normpath(t).lstrip("/")


def _cwd_ok(cwd) -> bool:
    """A working directory where deleting inside it is routine."""
    if not cwd:
        return False
    if any(cwd.startswith(r) and len(cwd) > len(r) for r in TEMP_ROOTS + (SCRATCH_ROOT,)):
        return True
    if not cwd.startswith(HOME + "/"):
        return False
    parts = cwd[len(HOME) + 1:].split("/")
    if parts[0] == "Projects":
        return len(parts) >= 2
    return len(parts) >= 2 and parts[0] not in UNSAFE_CWD_ROOTS


def _target(t: str, cwd, allow_cwd=False) -> str:
    """'ok', 'ask' or 'deny' for one recursive-delete target."""
    if not t:
        return "ask"
    if ".." in re.split(r"/+", t):
        return "deny"
    p = _expand(t, cwd)
    if p is None:
        return "ask"
    if not p.startswith("/"):  # cwd unknown
        return "ok" if any(x in BUILD_DIRS for x in p.split("/")) else "ask"
    if p == "/" or (HOME + "/").startswith(p.rstrip("/") + "/"):
        return "deny"  # /, /Users, ~
    parts = p.split("/")
    if ".git" in parts:
        return "ask"
    glob_only = bool(parts[-1]) and set(parts[-1]) <= set("*?.[]!")
    parent = os.path.dirname(p) if glob_only else p
    if p == TMP_MARK:
        return "ask"
    for root in TEMP_ROOTS:
        if p.startswith(root) and len(p) > len(root):
            return "ask" if parent + "/" == root else "ok"
    if p.startswith(PROJECTS + "/"):
        rel = p[len(PROJECTS) + 1:].split("/")
        if len(rel) >= 2 and "*" not in rel[0] and any(x in BUILD_DIRS for x in rel[1:]):
            return "ok"
    if p.startswith(HOME + "/Library/Developer/") and any(x in BUILD_DIRS for x in parts):
        return "ok"  # DerivedData
    if p.startswith(HOME + "/Library/Caches/") and len(p) > len(HOME + "/Library/Caches/") and not glob_only:
        return "ok"
    if _cwd_ok(cwd):
        if p.startswith(cwd.rstrip("/") + "/"):
            return "ask" if glob_only and parent == cwd.rstrip("/") else "ok"
        if allow_cwd and p == cwd.rstrip("/"):
            return "ok"
    return "deny"


def _rm_args(args):
    rec, targets, end = False, [], False
    for a in args:
        if not end and a == "--":
            end = True
        elif not end and a.startswith("--"):
            rec |= a == "--recursive"
        elif not end and a.startswith("-") and len(a) > 1:
            rec |= "r" in a or "R" in a
        else:
            targets.append(a)
    return rec, targets


def _find_starts(args):
    i = 0
    while i < len(args) and args[i] in ("-H", "-L", "-P", "-E", "-X", "-d", "-s", "-x"):
        i += 1
    starts = []
    while i < len(args) and not args[i].startswith(("-", "(", "!")):
        starts.append(args[i])
        i += 1
    return starts or ["."]


def _find_deletes(args) -> bool:
    return "-delete" in args or any(
        a in ("-exec", "-execdir", "-ok", "-okdir") and i + 1 < len(args) and _name(args[i + 1]) == "rm"
        for i, a in enumerate(args))


def _worst(verdicts):
    return max(verdicts, key=lambda v: {"ok": 0, "ask": 1, "deny": 2}[v], default="ok")


def _delete_verdict(name, args, xargs, producer, cwd) -> str:
    if name == "find" and _find_deletes(args):
        return _worst(_target(s, cwd, allow_cwd=True) for s in _find_starts(args))
    if name != "rm":
        return "ok"
    rec, targets = _rm_args(args)
    if not rec:
        return "ok"
    verdicts = [_target(t, cwd) for t in targets if t != "{}"]
    if xargs:
        pname, pargs = producer or ("", [])
        if pname in ("echo", "printf"):
            items = [x for x in pargs if not x.startswith("-")][1 if pname == "printf" else 0:]
            verdicts += [_target(x, cwd) for x in items] or ["ask"]
        elif pname == "find":
            verdicts += [_target(s, cwd, allow_cwd=True) for s in _find_starts(pargs)]
        else:
            verdicts.append("ask")  # names come from stdin
    return _worst(verdicts)


# ---------- secrets ----------

def _scan_tokens(name, args):
    """Arguments that may name a file this command reads."""
    if name in PATTERN_TOOLS:
        out, pattern_given, positional, i = [], False, [], 0
        while i < len(args):
            a = args[i]
            if a == "--":
                positional += args[i + 1:]
                break
            if a.startswith("-") and a != "-":
                if a in ("-e", "--regexp", "--expression"):
                    pattern_given = True
                    i += 2
                    continue
                if a in ("-f", "--file") and i + 1 < len(args):
                    pattern_given = True
                    out.append(args[i + 1])  # pattern/script file is read
                    i += 2
                    continue
                if a in ("--rawfile", "--slurpfile") and i + 2 < len(args):
                    out.append(args[i + 2])
                    i += 3
                    continue
                if a.startswith(("--file=", "--rawfile=", "--slurpfile=")):
                    out.append(a.split("=", 1)[1])
                elif a.startswith(("--regexp=", "--expression=")):
                    pattern_given = True
                elif a == "-i" and name == "sed" and i + 1 < len(args) and args[i + 1] == "":
                    i += 1  # BSD sed -i ''
                elif a in PATTERN_VALUE_FLAGS:
                    i += 1
                i += 1
                continue
            positional.append(a)
            i += 1
        return out + (positional if pattern_given else positional[1:])
    if name == "git":
        out, skip = [], False
        for a in args:
            if skip:
                skip = False
            elif a in ("-m", "--message"):
                skip = True
            elif not a.startswith("--message="):
                out.append(a)
        return out
    return [a for a in args if not a.startswith(("--exclude", "--ignore"))]


def _mentions_secret(text, cwd=None) -> bool:
    """A secret path in text, ignoring public key files and a project's own .claude/settings.json."""
    for m in SECRET_RE.finditer(text):
        start, end = m.start(), m.end()
        while start > 0 and text[start - 1] not in TOKEN_EDGE:
            start -= 1
        while end < len(text) and text[end] not in TOKEN_EDGE:
            end += 1
        token = text[start:end]
        plain = not set(token[2:] if token.startswith("~/") else token) & TOKEN_META
        if plain and PUBLIC_TOKEN.search(token) and "priv" not in token.lower():
            continue
        if plain and PROJECT_SETTINGS.search(token) and _project_file(token, cwd):
            continue
        return True
    return False


def _simple_command(text) -> bool:
    """One plain file command: no pipe, list, substitution, redirect, variable, directory flag or '..'."""
    if not text or any(ch in text for ch in ";&|`$\n\r<>(){}\\"):
        return False
    words = [word for _, word in _lex(text)]
    if not words or words[0] not in SIMPLE_READERS:
        return False
    return not any(".." in word.split("/") or word.startswith(("-C", "-c", "--git-dir", "--work-tree",
                                                                "--exec-path", "--namespace"))
                   for word in words[1:])


def _project_file(token, cwd) -> bool:
    """The path provably resolves inside a project or temp folder, not to a protected client config.

    A relative path counts only in one plain command, where nothing can move the directory it is read from.
    """
    if not cwd or ".." in token.split("/"):
        return False
    absolute = token.startswith(("/", "~/"))
    if not absolute and not _simple_command(_COMMAND):
        return False
    path = _expand(token, cwd)
    if path is None or not path.startswith("/"):
        return False
    real = os.path.realpath(path)
    roots = (PROJECTS + "/", SCRATCH_ROOT) + TEMP_ROOTS
    if not (any(real.startswith(root) for root in roots) and any(path.startswith(root) for root in roots)):
        return False
    return not _read_guard()["protected_path"](path, cwd)


def _inspector(name, args, cwd=None) -> bool:
    """Commands that may name a secret file without printing its contents."""
    flags = [a for a in args if a.startswith("-") and a != "-"]
    pos = [a for a in args if not a.startswith("-") or a == "-"]
    if name in ("ls", "test", "[", "[[", "stat", "shasum", "sha256sum", "md5", "chmod", "echo", "printf", "touch"):
        return True
    if name == "find":
        return not any(a in ("-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fls") for a in args)
    if name == "wc":
        return bool(flags) and all(f == "-c" for f in flags)
    if name == "jq":
        return bool(pos) and pos[0] in ("keys", "keys[]", "keys_unsorted")
    if name in ("grep", "egrep", "fgrep", "rg"):
        return any(f in ("--count", "--files-with-matches", "--files-without-match", "--quiet")
                   # -L lists non-matching files in grep but follows symlinks in ripgrep.
                   or (not f.startswith("--") and set(f[1:]) & set("clq" if name == "rg" else "clLq"))
                   for f in flags)
    if name in ("cp", "mv"):
        keeps = name == "mv" or any(not f.startswith("--") and "p" in f for f in flags)
        guard = _read_guard()
        # Both classifiers must call every name a secret, so a copy never lands under a readable name.
        if keeps and len(pos) >= 2 and all(
                _mentions_secret(p, cwd) and (guard["secret_name"](p) or _sensitive_file(p, cwd)) for p in pos):
            return True
        # cp .env.example .env: seed a new env file from a template. Never over an existing one.
        if (name == "cp" and len(pos) == 2 and cwd and not _mentions_secret(pos[0], cwd)
                and not _sensitive_file(pos[0], cwd) and not set(pos[0] + pos[1]) & TOKEN_META):
            target = _expand(pos[1], cwd)
            return bool(target) and target.startswith("/") and not os.path.lexists(target)
        return False
    if name == "git":
        sub = pos[0] if pos else ""
        return sub in ("check-ignore", "ls-files", "status") or (sub == "rm" and "--cached" in args)
    return False


@lru_cache(maxsize=1)
def _read_guard():
    # One classifier for native reads and recognized shell file readers.
    return runpy.run_path(os.path.join(os.path.dirname(__file__), "deny-env-read.py"))


def _sensitive_file(token, cwd) -> bool:
    path = _expand(token, cwd)
    if path is None:
        return False
    guard = _read_guard()
    return (guard["protected_path"](path, cwd or "") or guard["secret_name"](path)
            or guard["secret_name"](os.path.realpath(path)))


RG_VALUE_FLAGS = set("ABCEefgjmMrtTd")  # ripgrep short flags that take a value


def _search_options(name, args):
    """(respects gitignore, follows symlinks, globs) for a recursive search command.

    Every argument is read as a possible flag, including after "--": a misread
    only sends the search to the stricter full walk.
    """
    follow = False
    unrestricted = "RIPGREP_CONFIG_PATH" in _COMMAND or "RIPGREP_CONFIG_PATH" in os.environ
    globs, i = [], 0
    while i < len(args):
        a = args[i]
        following = args[i + 1] if i + 1 < len(args) else ""
        if a.startswith("--"):
            flag, eq, value = a.partition("=")
            if flag in ("--glob", "--iglob", "--include", "--exclude", "--exclude-dir"):
                if not eq:
                    value, i = following, i + 1
                globs.append(("!" if flag.startswith("--exclude") else "") + value)
            else:
                follow |= flag in ("--follow", "--dereference-recursive")
                unrestricted |= flag.startswith("--no-ignore") or flag in (
                    "--unrestricted", "--pre", "--pre-glob", "--ignore-file")
        elif a.startswith("-") and len(a) > 1:
            cluster = a[1:]
            for k, ch in enumerate(cluster):
                if name != "rg":
                    follow |= ch in "RS" or (name == "ag" and ch == "f")
                    continue
                if ch in RG_VALUE_FLAGS:
                    value = cluster[k + 1:]
                    if not value:
                        value, i = following, i + 1
                    if ch == "g":
                        globs.append(value)
                    break
                unrestricted |= ch == "u"
                follow |= ch == "L"
        i += 1
    # Only ripgrep is modelled as skipping gitignored files; ag, ack and grep get the full walk.
    return name == "rg" and not unrestricted, follow, globs


def _path_read_verdict(name, args, cwd) -> str:
    """The deny reason when this reader would open a secret file, else ''."""
    readers = {"cat", "head", "tail", "less", "more", "sed", "awk", "gawk",
               "jq", "yq", "grep", "egrep", "fgrep", "rg", "ag", "ack",
               "base64", "xxd", "strings", "od", "hexdump", "diff", "cmp"}
    if name not in readers or _inspector(name, args, cwd) or name == "rg" and "--files" in args:
        return ""
    guard = _read_guard()
    paths = [p for p in _scan_tokens(name, args) if not p.startswith("-")]
    for token in paths:
        if _sensitive_file(token, cwd):
            return R_SECRET
    recursive = name in {"rg", "ag", "ack"} or name in {"grep", "egrep", "fgrep"} and any(
        a in {"--recursive", "--dereference-recursive"}
        or a.startswith("-") and not a.startswith("--") and set(a[1:]) & set("rR") for a in args)
    if recursive:
        respect_ignore, follow, globs = _search_options(name, args)
        scopes = paths or ["."]
        # A "path" that does not exist is probably the pattern after a flag this parser
        # misread (rg -ig GLOB PATTERN), which leaves the working directory as the scope.
        if not all((_expand(t, cwd) or "").startswith("/") and os.path.lexists(_expand(t, cwd)) for t in scopes):
            scopes = scopes + ["."]
        for token in scopes:
            path = _expand(token, cwd)
            if path is None or guard["unsafe_search_scope"](path, cwd or os.getcwd(), respect_ignore, follow, globs):
                return guard["SCOPE_REASON"]
    return ""


def _secret_verdict(argv0, name, args, redirs, in_subst, pipe_has_runner, cwd="") -> str:
    """The deny reason when this command would read a secret, else ''."""
    for op, target in redirs:
        if op != "<<" and op not in (">>", "&>>") and (_mentions_secret(target, cwd) or _sensitive_file(target, cwd)):
            return R_SECRET  # read from, or truncate, a secret file
    reason = _path_read_verdict(name, args, cwd)
    if reason:
        return reason
    tokens = _scan_tokens(name, args)
    if not (_mentions_secret(argv0, cwd) or any(_mentions_secret(t, cwd) for t in tokens)):
        return ""
    return R_SECRET if in_subst or pipe_has_runner or not _inspector(name, args, cwd) else ""


# ---------- asks ----------

CURL_VALUE = set("ouHAebcxrmwKECDUYyztQP")
LOCAL_URL = re.compile(r"^(https?://)?(localhost|127\.0\.0\.1|\[::1\]|[\w.-]+\.localhost)(:\d+)?(/|$)", re.I)


def _curl_local(args) -> bool:
    """Every URL is a local dev server, so a write never leaves the machine."""
    urls = [a for a in args if "://" in a or LOCAL_URL.match(a)]
    return bool(urls) and all(LOCAL_URL.match(a) for a in urls)


def _curl_writes(args) -> bool:
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            n, eq, v = a.partition("=")
            if n == "--json" or n.startswith("--data") or n in ("--form", "--form-string", "--upload-file"):
                return True
            if n == "--request":
                method = v if eq else (args[i + 1] if i + 1 < len(args) else "")
                if method.upper() not in ("GET", "HEAD", "OPTIONS"):
                    return True
        elif a.startswith("-") and len(a) > 1:
            for k, ch in enumerate(a[1:], 1):
                if ch in "dFT":
                    return True
                if ch == "X":
                    method = a[k + 1:] or (args[i + 1] if i + 1 < len(args) else "")
                    if method.upper() not in ("GET", "HEAD", "OPTIONS"):
                        return True
                    if not a[k + 1:]:
                        i += 1
                    break
                if ch in CURL_VALUE:
                    if k == len(a) - 1:
                        i += 1
                    break
        i += 1
    return False


WRANGLER_BOOL = {"--remote", "--local", "--dry-run", "--minify", "--json", "--yes", "-y", "--preview", "--latest"}


def _wrangler_risky(args) -> bool:
    pos, prev = [], None
    for a in args:
        if a.startswith("-"):
            prev = a
            continue
        if prev and prev.startswith("--") and "=" not in prev and prev not in WRANGLER_BOOL:
            prev = None
            continue  # value of --env, --config, ...
        prev = None
        pos.append(a)
    p = (pos + ["", "", ""])[:3]
    if "--dry-run" in args and p[0] in ("deploy", "publish", "versions"):
        return False  # builds and reports, uploads nothing
    if p[0] in ("deploy", "publish", "rollback", "delete") or p[0].startswith("secret:"):
        return True
    if p[0] in ("pages", "versions", "triggers") and "deploy" in p[1:]:
        return True
    if "secret" in p and any(x in ("put", "bulk", "delete") for x in p):
        return True
    if p[0] in ("r2", "kv") or p[0].startswith(("kv:", "r2:")):
        return "--remote" in args  # Wrangler 4 kv/r2 commands default to local
    return p[0] == "d1" and p[1] in ("execute", "migrations") and "--remote" in args


def _gh_risky(args) -> bool:
    pos = [a for a in args if not a.startswith("-")]
    sub, sub2 = (pos + ["", ""])[:2]
    if sub == "api":
        method, fields, i = None, False, 0
        while i < len(args):
            a = args[i]
            if a in ("-X", "--method"):
                method = args[i + 1] if i + 1 < len(args) else ""
                i += 1
            elif a.startswith("--method="):
                method = a.split("=", 1)[1]
            elif a.startswith("-X"):
                method = a[2:]
            elif a in ("-f", "-F", "--field", "--raw-field", "--input") or a.startswith(
                    ("--field=", "--raw-field=", "--input=", "-f", "-F")):
                fields = True
            i += 1
        if method is not None:
            return method.upper() not in ("GET", "HEAD")
        if fields:  # fields switch gh api to POST; graphql reads stay silent
            return "graphql" not in pos or any("mutation" in a.lower() for a in args)
        return False
    return ((sub == "pr" and sub2 == "merge")
            or (sub == "release" and sub2 not in ("list", "view", "download", ""))
            or (sub == "repo" and sub2 in ("delete", "archive", "unarchive", "edit", "rename"))
            or (sub == "workflow" and sub2 == "run")
            or (sub == "secret" and sub2 in ("set", "delete", "remove")))


def _git_verdict(args):
    """Return (decision, reason) for one git command."""
    i, cfg = 0, []
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--exec-path"):
            if a == "-c" and i + 1 < len(args):
                cfg.append(args[i + 1])
            i += 2
            continue
        if a.startswith("-c"):
            cfg.append(a[2:])
        i += 1
    sub, rest = (args[i] if i < len(args) else ""), args[i + 1:]
    if sub == "push":
        level, pos, j, lease, wide = "allow", [], 0, False, False
        while j < len(rest):
            a = rest[j]
            if a == "--":
                pos += rest[j + 1:]
                break
            if a.startswith("--"):
                n = a.split("=")[0]
                if n == "--force":
                    return "deny", R_FORCE
                if n in ("--force-with-lease", "--force-if-includes"):
                    lease = True  # refuses to overwrite unseen work: ask, except on main
                wide |= n in ("--all", "--mirror", "--branches", "--tags")
                if n in ("--delete", "--mirror", "--prune"):
                    level = "ask"
                if n in ("--repo", "--receive-pack", "--exec", "--push-option") and "=" not in a:
                    j += 1
            elif a.startswith("-") and len(a) > 1:
                for k, ch in enumerate(a[1:], 1):
                    if ch == "f":
                        return "deny", R_FORCE
                    if ch == "d":
                        level = "ask"
                    if ch == "o":
                        j += k == len(a) - 1
                        break
            else:
                pos.append(a)
            j += 1
        if any(r.startswith("+") for r in pos):
            return "deny", R_FORCE
        if lease:
            # Only a named branch other than main can be approved; HEAD or no refspec may be main.
            targets = [r.split(":")[-1].split("/")[-1].lower() for r in pos[1:]]
            if wide or not targets or any(t in ("main", "master", "head", "@", "") for t in targets):
                return "deny", R_FORCE
            level = "ask"
        if any(r.startswith(":") for r in pos):
            level = "ask"
        if level == "ask":
            return "ask", R_ASK
    if any(re.search(r"core\.hookspath", c, re.I) for c in cfg) or "--no-verify" in rest:
        return "ask", R_ASK
    if sub == "reset" and "--hard" in rest:
        return "ask", R_ASK
    if sub == "commit":
        j = 0
        while j < len(rest):
            a = rest[j]
            if a == "--":
                break
            if a.startswith("--"):
                if a in ("--message", "--file", "--reuse-message", "--reedit-message", "--author", "--date",
                         "--template", "--fixup", "--squash", "--trailer", "--cleanup", "--pathspec-from-file"):
                    j += 1
            elif a.startswith("-") and len(a) > 1:
                for k, ch in enumerate(a[1:], 1):
                    if ch == "n":
                        return "ask", R_ASK
                    if ch in "mFCct":
                        j += k == len(a) - 1
                        break
                    if ch in "Su":
                        break
            j += 1
    return "allow", ""


def _script_arg(name, args):
    a = list(args)
    if name in ("bun", "deno") and a and a[0] == "run":
        a = a[1:]
    i = 0
    while i < len(a) and a[i].startswith("-"):
        if a[i] in ("-c", "-e", "--eval", "-p", "--print"):
            return None  # inline code
        if a[i] == "-m" and i + 1 < len(a):
            return a[i + 1]
        if a[i] in ("-r", "--require", "--import", "--loader", "-W", "-X"):
            i += 1
        i += 1
    return a[i] if i < len(a) else None


def _deploy_named(text) -> bool:
    """A script or task named for deploying, releasing, publishing or shipping."""
    parts = [p for p in text.split("/") if p not in ("", ".", "..")]
    if not parts:
        return False
    base = parts[-1]
    if SAFE_SCRIPT_WORD.search(base) and not JOINED_SCRIPT_WORD.search(base):
        return False
    if SCRIPT_WORD.search(base):
        return True
    # scripts/release/build.sh still counts; build output such as .build/release/tool does not.
    return bool(SCRIPT_EXT.search(base)) and any(
        SCRIPT_WORD.search(p) for p in parts[:-1]) and not any(
        p in BUILD_DIRS or p in ("Build", "Products") for p in parts[:-1])


def _ask_command(name, argv0, args) -> bool:
    # Parked hosts: any use needs Cohen, also through a wrapper (yarn vercel, doppler run -- vercel).
    if name in ("vercel", "netlify") or (name not in TEXT_ONLY and any(a in ("vercel", "netlify") for a in args)):
        return True
    if name == "curl":
        return _curl_writes(args) and not _curl_local(args)
    if name == "wrangler":
        return _wrangler_risky(args)
    if name == "gh":
        return _gh_risky(args)
    if name in ("npm", "pnpm", "yarn", "bun"):
        pos = [a for a in args if not a.startswith("-")]
        if pos[:1] == ["publish"]:
            return True
        if pos[:1] in (["run"], ["run-script"]) and len(pos) > 1 and _deploy_named(pos[1]):
            return True
        if name in ("pnpm", "yarn", "bun") and pos and _deploy_named(pos[0]):
            return True
    if name in ("make", "gmake", "just", "task", "mise", "rake"):
        pos, skip = [], False
        for a in args:
            if skip:
                skip = False
            elif a in ("-C", "-f", "-j", "-I", "-o", "-W", "--file", "--directory"):
                skip = True
            elif not a.startswith("-") and "=" not in a:
                pos.append(a)
        if any(_deploy_named(t) for t in pos):
            return True
    if name in INTERPRETERS:
        script = _script_arg(name, args)
        # Ship's default operation only plans. Keep Apply and unknown arguments
        # gated; do not exempt other scripts merely because they share a name.
        if name in ("python", "python3") and args and script == args[0]:
            plans = {
                HOME + "/.agents/skills/ship/scripts/ship.py",
                HOME + "/Projects/Agent Skills/skills/ship/scripts/ship.py",
            }
            if (os.path.expanduser(script) in plans
                    and all(a in ("--plan-only", "--skip-fetch", "--json", "--help", "-h",
                                  "--verify-only", "--cleanup-report", "--all", "--status")
                            for a in args[1:])):
                return False
        if script and _deploy_named(script):
            return True
    if "/" in argv0 and _deploy_named(argv0):
        return True  # ./deploy.sh, scripts/release/x.sh
    if _deploy_named(name) and re.search(r"\.(sh|py|js|mjs|cjs|ts|rb|pl)$", name):
        return True
    # Notarize, staple and export stay local or private; only altool uploads to App Store Connect.
    if name == "xcrun":
        pos = [a for a in args if not a.startswith("-")]
        return pos[:1] == ["altool"]
    return name == "altool"


def _nested(name, args):
    """Command strings run by a wrapper: bash -c STR, eval STR, ssh host CMD, watch CMD."""
    if name in SHELLS:
        for i, a in enumerate(args):
            if a.startswith("-") and not a.startswith("--") and "c" in a and i + 1 < len(args):
                return [args[i + 1]]
        return []
    if name == "eval":
        return [" ".join(args)]
    if name == "watch":
        return [" ".join(a for a in args if not a.startswith("-"))]
    if name == "ssh":
        pos = [a for a in args if not a.startswith("-")]
        return [" ".join(pos[1:])] if len(pos) > 1 else []
    if name == "tmux" and args[:1] in (["send-keys"], ["send"]):
        return [" ".join(a for a in args[1:] if not a.startswith("-"))]
    return []


def _cd(args, cwd):
    args = [a for a in args if a not in ("-P", "-L", "--")]
    if not args:
        return HOME
    if args[0] == "-":
        return None
    p = _expand(args[0], cwd)
    return p if p and p.startswith("/") else None


def analyze(text: str, cwd, depth=0, in_subst=False) -> Verdict:
    v = Verdict()
    if depth > 6:
        v.add("ask", R_ASK)
        return v
    text, inner = _extract_subst(text)
    for sub in inner:
        v.merge(analyze(sub, cwd, depth + 1, True))
    segs = _segments(_lex(text))
    norm = [_normalize(s["argv"]) for s in segs]
    for idx, seg in enumerate(segs):
        argv, xargs = norm[idx]
        if not argv:
            if any(op != "<<" and op not in (">>", "&>>") and _mentions_secret(t, cwd) for op, t in seg["redirs"]):
                v.add("deny", R_SECRET)
            continue
        argv0, name, args = argv[0], _name(argv[0]), argv[1:]
        if name in ("cd", "pushd", "chdir"):
            if not in_subst:
                cwd = _cd(args, cwd)
            continue
        v.names.add(name)
        same_pipe = [j for j, s in enumerate(segs) if s["pipe"] == seg["pipe"] and j != idx]
        runner = any(norm[j][1] or (norm[j][0] and _name(norm[j][0][0]) in RUNNERS) for j in same_pipe)
        secret_reason = _secret_verdict(argv0, name, args, seg["redirs"], in_subst, runner, cwd)
        if secret_reason:
            v.add("deny", secret_reason)
        producer = None
        if xargs and idx > 0 and segs[idx - 1]["pipe"] == seg["pipe"] and norm[idx - 1][0]:
            producer = (_name(norm[idx - 1][0][0]), norm[idx - 1][0][1:])
        rm = _delete_verdict(name, args, xargs, producer, cwd)
        if rm == "deny":
            v.add("deny", R_RM)
        elif rm == "ask":
            v.add("ask", R_RM_ASK)
        if name == "git":
            v.add(*_git_verdict(args))
        elif _ask_command(name, argv0, args):
            v.add("ask", R_ASK)
        for nested in _nested(name, args):
            v.merge(analyze(nested, cwd, depth + 1, in_subst))
    return v


def _command(data: dict) -> str:
    tool_input = data.get("toolInput") or data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    return str(data.get("command") or tool_input.get("command") or "")


def _approval_path(cwd: str, command: str) -> str:
    key = hashlib.sha256((os.path.realpath(cwd or os.getcwd()) + "\0" + command).encode()).hexdigest()
    return os.path.join(HOME, ".agents", "hooks", "approvals", key + ".json")


def _consume_approval(cwd: str, command: str) -> bool:
    """Consume a one-use, short-lived approval for this exact command and cwd."""
    path = _approval_path(cwd, command)
    claimed = path + ".used-" + str(os.getpid())
    try:
        os.rename(path, claimed)
    except FileNotFoundError:
        return False
    try:
        fd = os.open(claimed, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            receipt = json.load(handle)
        expected = hashlib.sha256((os.path.realpath(cwd or os.getcwd()) + "\0" + command).encode()).hexdigest()
        return receipt.get("command_hash") == expected and receipt.get("expires_at", 0) >= time.time()
    except (OSError, ValueError, TypeError):
        return False
    finally:
        try:
            os.unlink(claimed)
        except FileNotFoundError:
            pass


def decide(cmd: str, cwd: str = ""):
    global _COMMAND
    _COMMAND = cmd
    # Pure literal output is documentation, not a command inside its text.
    # Keep substitutions, redirections, compound commands, and scripts guarded.
    if not any(char in cmd for char in ("$", "`", "\n", "\r")):
        toks = _lex(cmd)
        if toks and toks[0] == ("w", "echo") or toks[:1] == [("w", "printf")]:
            if all(kind == "w" for kind, _ in toks):
                return "allow", ""
    shell, code = _split_heredocs(cmd)
    if _mentions_secret(code, cwd):
        return "deny", R_SECRET
    if any(re.search(p, shell, re.I) for p in SECRET_COMMANDS):
        return "deny", R_ENV
    v = analyze(shell, cwd or None)
    if v.decision != "deny" and any(re.search(p, shell, re.I) for p in ASK):
        v.add("ask", R_ASK)
    # SQL that reaches a database client by argument, pipe or here-string; not text git or grep only stores.
    if DROP_SQL.search(shell) and not v.names <= TEXT_ONLY:
        v.add("ask", R_ASK)
    if v.decision == "ask" and _consume_approval(cwd, cmd):
        return "allow", ""
    return v.decision, v.reason


PATCH_PATH = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): *(.+?) *$", re.M)
JS_COMMAND = re.compile(
    r"(?:\b(?:execSync|execFileSync|spawnSync|exec|execFile|spawn)\s*\(\s*|\bcmd\s*:\s*)"
    r"([\"'`])((?:\\.|(?!\1)[^\\])*)\1", re.S)


def decide_patch(patch: str, cwd: str = ""):
    """apply_patch (Codex) or Edit/Write: deny a patch that touches a secret path."""
    if any(_mentions_secret(p, cwd) for p in PATCH_PATH.findall(patch)):
        return "deny", R_SECRET
    return "allow", ""


def decide_code(code: str, cwd: str = ""):
    """Codex js (node REPL) code: deny secret mentions; judge shell commands it runs."""
    global _COMMAND
    _COMMAND = code
    if _mentions_secret(code, cwd):
        return "deny", R_SECRET
    v = Verdict()
    for _, cmd in JS_COMMAND.findall(code):
        v.add(*decide(cmd.encode().decode("unicode_escape", "ignore"), cwd))
    return v.decision, v.reason


FILE_TOOLS = {
    "apply_patch", "Edit", "Write", "MultiEdit",
    "write", "search_replace", "StrReplace",
}
PATH_KEYS = ("file_path", "filePath", "path", "file", "target_file")
R_TRUNCATED = "Tool input was truncated, so the guard cannot see the whole call."


def _joined_paths(data, ti) -> str:
    parts = []
    for key in PATH_KEYS:
        for src in (ti, data):
            value = src.get(key)
            if value:
                parts.append(str(value))
    return " ".join(parts)


def route(data: dict):
    if data.get("toolInputTruncated") is True or data.get("tool_input_truncated") is True:
        return "deny", R_TRUNCATED
    global _COMMAND
    _COMMAND = ""
    tool = str(data.get("tool_name") or data.get("toolName") or "")
    ti = data.get("toolInput") or data.get("tool_input") or {}
    if not isinstance(ti, dict):
        ti = {}
    cwd = str(data.get("cwd") or "")
    if tool in FILE_TOOLS:
        text = ti.get("command") or ti.get("patch") or ti.get("input") or data.get("input") or ""
        if isinstance(text, list):
            text = "\n".join(map(str, text))
        paths = _joined_paths(data, ti)
        if paths.strip() and _mentions_secret(paths, cwd):
            return "deny", R_SECRET
        return decide_patch(str(text), cwd)
    if tool in ("js", "node_repl", "js_repl") or ("code" in ti and not _command(data)):
        return decide_code(str(ti.get("code") or ""), cwd)
    return decide(_command(data), cwd)


def main() -> None:
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError("hook input is not an object")
        decision, reason = route(data)
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
