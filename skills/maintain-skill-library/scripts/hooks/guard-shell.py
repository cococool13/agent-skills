#!/usr/bin/python3
"""One shell guard for Claude, Cursor, Grok, and Codex. Fail closed.

The verdict comes from every simple command in the text (after ;, &&, |, $( ),
backticks, bash -c, eval), not from the command prefix.
deny: any mention of a secret path (except ls/test/stat/wc -c/shasum/jq keys/grep -c/
      chmod/cp -p/mv of it), env dumps, Keychain, gh token, live Stripe, force-push,
      rm -r / find -delete / xargs rm outside $PWD, ~/Projects/<repo> build dirs, or temp dirs.
ask:  deploys, releases, publishes, App Store uploads, merges, remote curl/gh api writes,
      git --no-verify / -n / reset --hard / push --delete, deploy-named scripts.
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
    r"\bdrop\s+(database|table)\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bvercel\b",
    r"\bnetlify\b",
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

SCRIPT_WORD = re.compile(r"(?<![a-z])(deploy|release|publish|ship)(?![a-z])", re.I)
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
INTERPRETERS = SHELLS | {"node", "python", "python3", "ruby", "perl", "bun", "deno", "tsx", "ts-node", "php"}
RUNNERS = SHELLS | {"eval", "source", ".", "parallel", "read"}
PATTERN_TOOLS = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "sed", "awk", "gawk", "jq", "yq"}
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
R_FORCE = "Force-push is blocked. Push a new branch or ask Cohen."
R_RM = "Recursive delete is allowed only inside the working directory, ~/Projects/<repo> build dirs, or temp dirs."
R_RM_ASK = "Recursive delete with an unresolved target. Wait for Cohen's approval."
R_ASK = "Deploy, release, publish, submit, merge, remote write, or destructive git. State the exact target and wait for Cohen's approval."


class Verdict:
    def __init__(self):
        self.decision, self.reason = "allow", ""

    def add(self, decision, reason):
        if LEVEL[decision] > LEVEL[self.decision]:
            self.decision, self.reason = decision, reason

    def merge(self, other):
        self.add(other.decision, other.reason)


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
    if any(cwd.startswith(r) and len(cwd) > len(r) for r in TEMP_ROOTS):
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


def _inspector(name, args) -> bool:
    """Commands that may name a secret file without printing its contents."""
    flags = [a for a in args if a.startswith("-") and a != "-"]
    pos = [a for a in args if not a.startswith("-") or a == "-"]
    if name in ("ls", "test", "[", "[[", "stat", "shasum", "sha256sum", "md5", "chmod", "echo", "printf"):
        return True
    if name == "find":
        return not any(a in ("-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fls") for a in args)
    if name == "wc":
        return bool(flags) and all(f == "-c" for f in flags)
    if name == "jq":
        return bool(pos) and pos[0] in ("keys", "keys[]", "keys_unsorted")
    if name in ("grep", "egrep", "fgrep", "rg"):
        return any(f in ("--count", "--files-with-matches", "--files-without-match", "--quiet")
                   or (not f.startswith("--") and set(f[1:]) & set("clLq")) for f in flags)
    if name in ("cp", "mv"):
        keeps = name == "mv" or any(not f.startswith("--") and "p" in f for f in flags)
        return keeps and len(pos) >= 2 and all(SECRET_RE.search(p) for p in pos)
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


def _path_read_verdict(name, args, cwd) -> bool:
    readers = {"cat", "head", "tail", "less", "more", "sed", "awk", "gawk",
               "jq", "yq", "grep", "egrep", "fgrep", "rg", "ag", "ack",
               "base64", "xxd", "strings", "od", "hexdump", "diff", "cmp"}
    if name not in readers or _inspector(name, args) or name == "rg" and "--files" in args:
        return False
    guard = _read_guard()
    paths = [p for p in _scan_tokens(name, args) if not p.startswith("-")]
    for token in paths:
        if _sensitive_file(token, cwd):
            return True
    recursive = name in {"rg", "ag", "ack"} or name in {"grep", "egrep", "fgrep"} and any(
        a in {"--recursive", "--dereference-recursive"}
        or a.startswith("-") and not a.startswith("--") and set(a[1:]) & set("rR") for a in args)
    if recursive:
        for token in paths or ["."]:
            path = _expand(token, cwd)
            if path is None or guard["unsafe_search_scope"](path, cwd or os.getcwd()):
                return True
    return False


def _secret_verdict(argv0, name, args, redirs, in_subst, pipe_has_runner, cwd="") -> bool:
    for op, target in redirs:
        if op != "<<" and op not in (">>", "&>>") and (SECRET_RE.search(target) or _sensitive_file(target, cwd)):
            return True  # read from, or truncate, a secret file
    if _path_read_verdict(name, args, cwd):
        return True
    if not (SECRET_RE.search(argv0) or any(SECRET_RE.search(t) for t in _scan_tokens(name, args))):
        return False
    return in_subst or pipe_has_runner or not _inspector(name, args)


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
        level, pos, j = "allow", [], 0
        while j < len(rest):
            a = rest[j]
            if a == "--":
                pos += rest[j + 1:]
                break
            if a.startswith("--"):
                n = a.split("=")[0]
                if n in ("--force", "--force-with-lease", "--force-if-includes"):
                    return "deny", R_FORCE
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


def _ask_command(name, argv0, args) -> bool:
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
        if pos[:1] in (["run"], ["run-script"]) and len(pos) > 1 and SCRIPT_WORD.search(pos[1]):
            return True
        if name in ("pnpm", "yarn", "bun") and pos and SCRIPT_WORD.search(pos[0]):
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
        if any(SCRIPT_WORD.search(t) for t in pos):
            return True
    if name in INTERPRETERS:
        script = _script_arg(name, args)
        if script and SCRIPT_WORD.search(script):
            return True
    if "/" in argv0 and SCRIPT_WORD.search(argv0):
        return True  # ./deploy.sh, scripts/release/x.sh
    if SCRIPT_WORD.search(name) and re.search(r"\.(sh|py|js|mjs|cjs|ts|rb|pl)$", name):
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
            if any(op != "<<" and op not in (">>", "&>>") and SECRET_RE.search(t) for op, t in seg["redirs"]):
                v.add("deny", R_SECRET)
            continue
        argv0, name, args = argv[0], _name(argv[0]), argv[1:]
        if name in ("cd", "pushd"):
            if not in_subst:
                cwd = _cd(args, cwd)
            continue
        same_pipe = [j for j, s in enumerate(segs) if s["pipe"] == seg["pipe"] and j != idx]
        runner = any(norm[j][1] or (norm[j][0] and _name(norm[j][0][0]) in RUNNERS) for j in same_pipe)
        if _secret_verdict(argv0, name, args, seg["redirs"], in_subst, runner, cwd):
            v.add("deny", R_SECRET)
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
    # Pure literal output is documentation, not a command inside its text.
    # Keep substitutions, redirections, compound commands, and scripts guarded.
    if not any(char in cmd for char in ("$", "`", "\n", "\r")):
        toks = _lex(cmd)
        if toks and toks[0] == ("w", "echo") or toks[:1] == [("w", "printf")]:
            if all(kind == "w" for kind, _ in toks):
                return "allow", ""
    shell, code = _split_heredocs(cmd)
    if SECRET_RE.search(code):
        return "deny", R_SECRET
    if any(re.search(p, shell, re.I) for p in SECRET_COMMANDS):
        return "deny", R_ENV
    v = analyze(shell, cwd or None)
    if v.decision != "deny" and any(re.search(p, shell, re.I) for p in ASK):
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
    if any(SECRET_RE.search(p) for p in PATCH_PATH.findall(patch)):
        return "deny", R_SECRET
    return "allow", ""


def decide_code(code: str, cwd: str = ""):
    """Codex js (node REPL) code: deny secret mentions; judge shell commands it runs."""
    if SECRET_RE.search(code):
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
        if paths.strip() and SECRET_RE.search(paths):
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
