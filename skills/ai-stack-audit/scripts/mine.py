#!/usr/bin/env python3
# ai-stack-audit phase5 copy of ~/Projects/_review/ai-stack-audit-2026-10-19/mine.py (2026-10-19), unchanged below this line.
# Aggregate-only transcript miner. Read-only; writes only --out. Self-test: python3 -I mine.py --selftest
"""mine.py: aggregate-only miner for Claude Code and Codex session transcripts.

Privacy contract
- Never prints or writes message text, tool inputs or tool outputs.
- Raw text is read only in memory, secret patterns are redacted first, then it is
  reduced to a short normalized signature (<=80 chars) or a bare binary/skill name.
- Output: aggregates plus transcript file paths.

Usage
  python3 -I mine.py [--out mine-output.json] [--git] [--claude-root DIR] [--codex-root DIR]
  python3 -I mine.py --selftest
"""
import argparse, collections, datetime as dt, glob, json, os, re, subprocess, sys, tempfile

HOME = os.path.expanduser("~")
TODAY = dt.datetime(2026, 10, 19, 23, 59, tzinfo=dt.timezone.utc)

# ---------------------------------------------------------------- redaction
SECRET_RES = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), re.compile(r"sk_(live|test)_[A-Za-z0-9]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{10,}"), re.compile(r"github_pat_[A-Za-z0-9_]{10,}"),
    re.compile(r"xox[abposr]-[A-Za-z0-9\-]{6,}"), re.compile(r"AKIA[0-9A-Z]{12,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-~+/=]{6,}"), re.compile(r"(?i)(token|key|secret|password|passwd|auth)[\"']?\s*[=:]\s*[^\s,;\"'&]+"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}(\.[A-Za-z0-9_\-]+)?"),
    re.compile(r"\b[0-9a-fA-F]{32,}\b"), re.compile(r"[A-Za-z0-9+/_\-]{32,}={0,2}"),
]

def redact(s):
    for r in SECRET_RES:
        s = r.sub("<redacted>", s)
    return s

PATH_RE = re.compile(r"(~|\.{1,2})?/[^\s'\"`:,;()\[\]{}<>]+")
HEXH_RE = re.compile(r"\b[0-9a-f]{7,}\b")
URL_RE = re.compile(r"https?://\S+")

def signature(text, n=80):
    """Redact, keep the first non-empty line, strip paths/urls/digits/hashes, cap length."""
    if not text:
        return ""
    s = redact(text[:600])
    line = ""
    for ln in s.splitlines():
        ln = ln.strip()
        if ln and not ln.startswith(("<tool_use_error>", "</tool_use_error>")):
            line = ln
            break
        if ln.startswith("<tool_use_error>"):
            line = ln[len("<tool_use_error>"):].strip()
            if line:
                break
    line = line.replace("</tool_use_error>", "")
    line = URL_RE.sub("<url>", line)
    line = PATH_RE.sub("<path>", line)
    line = HEXH_RE.sub("<h>", line)
    line = re.sub(r"\d+", "#", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line[:n]

WORD_RE = re.compile(r"^[A-Za-z0-9._+\-]{1,30}$")
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WRAPPERS = {"sudo", "time", "env", "command", "nohup", "exec", "xargs", "caffeinate"}

def bash_bin(cmd):
    """Return (binary, subcommand) of the main command; names only, never arguments."""
    if not isinstance(cmd, str):
        return ("?", "")
    segs = re.split(r"&&|\|\||;|\n", cmd)
    for seg in segs:
        toks = seg.strip().split()
        while toks and (ENV_ASSIGN.match(toks[0]) or toks[0] in WRAPPERS or toks[0].startswith("-")):
            toks = toks[1:]
        if not toks:
            continue
        b = os.path.basename(toks[0].strip("'\"("))
        if b in ("cd", "export", "set", "source", ".", "pushd", "echo", "sleep", "true", "local"):
            continue
        b = b if WORD_RE.match(b) else "<other>"
        sub = toks[1] if len(toks) > 1 and re.match(r"^[a-z][a-z0-9:_\-]{0,24}$", toks[1]) else ""
        return (b, sub)
    return ("cd/echo-only", "")

CNF_RES = [re.compile(r"command not found: ([A-Za-z0-9._+\-]{1,30})"),
           re.compile(r"(?:^|\s)([A-Za-z0-9._+\-]{1,30}): command not found"),
           re.compile(r"(?:^|\s)([A-Za-z0-9._+\-]{1,30}): not found")]

BUILD_CLASSES = [
    ("codesign", re.compile(r"(?i)code ?sign|provisioning profile|no signing certificate")),
    ("no-destination", re.compile(r"(?i)unable to find a destination|no simulator|destination specifier")),
    ("missing-module", re.compile(r"(?i)no such module|cannot find module|module not found|could not resolve")),
    ("swift-compile", re.compile(r"(?i)\.swift:\d+:\d+: error|swiftcompile|compiling .* failed")),
    ("type-error", re.compile(r"(?i)type error|TS\d{4}|is not assignable")),
    ("auth", re.compile(r"(?i)not logged in|authentication|unauthori[sz]ed|\b401\b|\b403\b|login required")),
    ("config", re.compile(r"(?i)wrangler\.(toml|jsonc?)|missing .*config|invalid config|no such file or directory")),
    ("timeout", re.compile(r"(?i)timed? ?out|timeout")),
    ("build-failed-generic", re.compile(r"(?i)build failed|\*\* build failed \*\*|error:|failed")),
]
BUILD_BINS = {"xcodebuild", "wrangler", "astro", "next", "xcrun", "swift", "xcodegen", "npm", "pnpm", "bun", "npx", "bunx", "vite", "tsc"}

CORRECTION_RE = re.compile(r"^(no\b|nope|don'?t|do not|stop|i said|i told you|use |not that|wrong|never |why did you|you didn'?t|that'?s not|still )")
FRUSTRATION_RE = re.compile(r"^(no\b|nope|wrong|stop|why|wtf|ugh|again|still (broken|not|doesn|wrong)|that'?s not|not what|this is (still )?(broken|wrong)|i said|i told you)")
THEMES = [
    ("browser/qa tooling", r"browser|chrome|ego|screenshot|playwright|pane|tab"),
    ("git/deploy/ship", r"commit|push|deploy|ship|branch|merge|pr\b|wrangler|release"),
    ("design/copy rules", r"subtitle|copy|text|font|icon|design|color|layout|button|tagline|word"),
    ("scope/over-building", r"don'?t (add|change|touch|create)|only|just|scope|simple|less|smaller"),
    ("asking vs doing", r"ask|permission|continue|keep going|do it|just do"),
    ("model/agent choice", r"model|sonnet|opus|fable|haiku|agent|subagent|codex|cursor|grok"),
    ("package manager/tooling", r"\bnpm\b|\bbun\b|pnpm|yarn|npx|brew|install"),
    ("testing/verification", r"test|verify|check|run it"),
]

def theme_of(sig):
    for name, rx in THEMES:
        if re.search(rx, sig):
            return name
    return "other"

def norm_prompt(text):
    t = redact(text.strip().lower())
    t = URL_RE.sub("", t)
    t = PATH_RE.sub("", t)
    t = re.sub(r"[0-9]+", "", t)
    t = re.sub(r"[^a-z' ]+", " ", t)
    return " ".join(t.split()[:6])

# ---------------------------------------------------------------- pricing
# USD per MTok: (input, cache_write_5m, cache_write_1h, cache_read, output)
# Source: platform.claude.com/docs/en/about-claude/pricing, fetched 2026-10-19.
PRICES = [
    ("claude-fable-5-1", (10, 12.5, 20, 0.25, 50)),
    ("claude-mythos-5-1", (10, 12.5, 20, 0.25, 50)),
    ("claude-fable-5", (10, 12.5, 20, 1.0, 50)),
    ("claude-opus-5-5", (4, 5, 8, 0.20, 20)),
    ("claude-opus-5", (5, 6.25, 10, 0.50, 25)),
    ("claude-opus-4", (5, 6.25, 10, 0.50, 25)),
    ("claude-sonnet-5-5", (2, 2.5, 4, 0.10, 10)),
    ("claude-sonnet-5", (2, 2.5, 4, 0.20, 10)),
    ("claude-sonnet-4", (3, 3.75, 6, 0.30, 15)),
    ("claude-haiku-5-5", (0.10, 0.125, 0.20, 0.01, 0.50)),
    ("claude-haiku-4-5", (1, 1.25, 2, 0.10, 5)),
]
HAIKU55_LONG = (0.50, 0.625, 1.0, 0.05, 2.50)  # prompts > 100K tokens
FAST = {"claude-opus-5-5": (8, 10, 16, 0.40, 40), "claude-opus-5": (10, 12.5, 20, 1.0, 50)}

def price_for(model, prompt_tokens, speed):
    if speed == "fast":
        for k, v in FAST.items():
            if model.startswith(k):
                return v
    if model.startswith("claude-haiku-5-5") and prompt_tokens > 100_000:
        return HAIKU55_LONG
    for k, v in PRICES:
        if model.startswith(k):
            return v
    return None

def family(model):
    for f in ("fable", "mythos", "opus", "sonnet", "haiku"):
        if f in (model or ""):
            return f
    return model or "unknown"

def cost_usd(u, model):
    inp, c5, c1, cr, out, speed, geo = u
    p = price_for(model, inp + c5 + c1 + cr, speed)
    if p is None:
        return None
    c = (inp * p[0] + c5 * p[1] + c1 * p[2] + cr * p[3] + out * p[4]) / 1e6
    if geo == "us":
        c *= 1.1
    return c

# ---------------------------------------------------------------- helpers
def parse_ts(s):
    if not isinstance(s, str):
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def week(ts):
    y, w, _ = ts.isocalendar()
    return f"{y}-W{w:02d}"

def project_of(cwd):
    if not isinstance(cwd, str) or not cwd:
        return "unknown"
    p = cwd.replace(HOME, "~")
    m = re.match(r"~/Projects/([^/]+)", p)
    if m:
        return m.group(1)
    if "scratch-workspaces" in p:
        return "<claude-scratch>"
    if p.startswith(("/private/var", "/var/folders", "/tmp", "/private/tmp")):
        return "<tmp>"
    if p == "~":
        return "~"
    return os.path.basename(p.rstrip("/")) or p

def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for x in content:
            if isinstance(x, dict) and x.get("type") == "text" and isinstance(x.get("text"), str):
                parts.append(x["text"])
        return "\n".join(parts)
    return ""

C = collections.Counter
DD = collections.defaultdict

def new_session(path, client):
    return {"path": path, "client": client, "start": None, "end": None, "active_s": 0.0, "_last": None,
            "cwd": C(), "models": C(), "tools": C(), "tool_calls": 0, "tool_errors": 0, "bash_bins": C(),
            "compactions": 0, "interrupts": 0, "user_prompts": 0, "last_user_sig": "", "last_user_kind": "",
            "sidechain": False, "entrypoint": C(), "session_id": None, "git_commit_calls": 0,
            "assistant_msgs": 0, "retry_loops": 0, "api_errors": 0, "cost_state_usd": None}

def touch(s, ts):
    if ts is None:
        return
    if s["start"] is None or ts < s["start"]:
        s["start"] = ts
    if s["end"] is None or ts > s["end"]:
        s["end"] = ts
    if s["_last"] is not None:
        gap = (ts - s["_last"]).total_seconds()
        if 0 < gap <= 900:
            s["active_s"] += gap
    s["_last"] = ts

# ---------------------------------------------------------------- Claude
def mine_claude(root, A):
    files = sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True))
    A["meta"]["claude_files"] = len(files)
    msg_usage = {}       # message.id -> [inp,c5,c1,cr,out,speed,geo, model, sesskey, ts, proj, sidechain, skill]
    tool_uses = {}       # tool_use_id -> (name, sesskey, ts, model, proj, bin, sub)
    seen_results = set()
    for f in files:
        S = new_session(f, "claude")
        S["sidechain"] = "/subagents/" in f
        prev_err = None
        streak = 0
        try:
            fh = open(f, "r", errors="replace")
        except OSError:
            A["meta"]["unreadable"] += 1
            continue
        with fh:
            for line in fh:
                A["meta"]["lines"] += 1
                try:
                    r = json.loads(line)
                except Exception:
                    A["meta"]["bad_json"] += 1
                    continue
                if not isinstance(r, dict):
                    continue
                t = r.get("type")
                ts = parse_ts(r.get("timestamp"))
                if t in ("user", "assistant", "system"):
                    touch(S, ts)
                if isinstance(r.get("cwd"), str):
                    S["cwd"][r["cwd"]] += 1
                if r.get("isSidechain") is True:
                    S["sidechain"] = True
                if isinstance(r.get("entrypoint"), str):
                    S["entrypoint"][r["entrypoint"]] += 1
                if isinstance(r.get("permissionMode"), str) and len(r["permissionMode"]) < 30:
                    S["pmode"] = r["permissionMode"]
                    A["perm_modes"][r["permissionMode"]] += 1
                if S["session_id"] is None and isinstance(r.get("sessionId"), str):
                    S["session_id"] = r["sessionId"]
                proj = project_of(r.get("cwd")) if r.get("cwd") else (project_of(S["cwd"].most_common(1)[0][0]) if S["cwd"] else "unknown")

                if t == "cost-state":
                    v = r.get("totalCostUSD")
                    if isinstance(v, (int, float)):
                        S["cost_state_usd"] = max(S["cost_state_usd"] or 0, v)
                    continue
                if t == "system":
                    st = r.get("subtype")
                    A["system_subtypes"][str(st)] += 1
                    if st == "compact_boundary":
                        S["compactions"] += 1
                    elif st == "api_error":
                        S["api_errors"] += 1
                        e = r.get("error")
                        key = "?"
                        if isinstance(e, dict):
                            key = str(e.get("status") or e.get("type") or (e.get("error") or {}).get("type") if isinstance(e.get("error"), dict) else e.get("status") or e.get("type"))
                        A["api_errors"][signature(str(key), 40)] += 1
                    elif st == "stop_hook_summary":
                        he = r.get("hookErrors")
                        if isinstance(he, list) and he:
                            A["hooks"]["stop_hook_errors"] += len(he)
                        if r.get("preventedContinuation"):
                            A["hooks"]["stop_hook_prevented_continuation"] += 1
                    continue
                if t == "attachment":
                    a = r.get("attachment")
                    if isinstance(a, dict):
                        at = a.get("type")
                        if isinstance(at, str) and at.startswith("hook"):
                            ev = a.get("hookEvent") if isinstance(a.get("hookEvent"), str) else ""
                            hn = a.get("hookName") if isinstance(a.get("hookName"), str) and len(a.get("hookName")) < 60 else ""
                            A["hooks"]["attachment:" + at] += 1
                            if at in ("hook_non_blocking_error", "hook_blocking_error", "hook_error"):
                                A["hook_errors_by_hook"][signature(f"{ev} {hn}", 60) or "?"] += 1
                                A["hook_error_keys"][",".join(sorted(a.keys()))[:120]] += 1
                                raw = a.get("stderr") or a.get("content") or a.get("error") or ""
                                ec = a.get("exitCode")
                                A["hook_error_sigs"][f"{hn} exit={ec} :: " + signature(raw if isinstance(raw, str) else "", 70)] += 1
                                if ts:
                                    A["hook_error_days"][ts.isoformat()[:10]] += 1
                        if at in ("compact_file_reference",):
                            pass
                    continue
                if r.get("isCompactSummary"):
                    S["compactions"] += 0  # counted via compact_boundary; kept for clarity
                    A["meta"]["compact_summaries"] += 1
                pdn = r.get("permissionDecision")
                m = r.get("message") if isinstance(r.get("message"), dict) else None
                content = m.get("content") if m else None

                if t == "assistant" and m:
                    model = m.get("model") or "unknown"
                    mid = m.get("id")
                    u = m.get("usage")
                    if model != "<synthetic>" and isinstance(u, dict) and mid:
                        cc = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else {}
                        ccin = u.get("cache_creation_input_tokens") or 0
                        c1 = cc.get("ephemeral_1h_input_tokens") or 0
                        c5 = max(ccin - c1, 0)
                        vals = [u.get("input_tokens") or 0, c5, c1, u.get("cache_read_input_tokens") or 0, u.get("output_tokens") or 0]
                        A["usage_flags"]["speed:" + str(u.get("speed"))] += 1
                        A["usage_flags"]["geo:" + str(u.get("inference_geo"))] += 1
                        A["usage_flags"]["tier:" + str(u.get("service_tier"))] += 1
                        sk = r.get("attributionSkill") if isinstance(r.get("attributionSkill"), str) else ""
                        prev = msg_usage.get(mid)
                        if prev is None:
                            msg_usage[mid] = vals + [u.get("speed"), u.get("inference_geo"), model, f, ts, proj, S["sidechain"] or bool(r.get("isSidechain")), sk]
                            S["assistant_msgs"] += 1
                            S["models"][model] += 1
                        elif prev[8] == f:
                            for i in range(5):
                                prev[i] = max(prev[i], vals[i])
                        else:
                            A["meta"]["dup_msg_other_file"] += 1
                    if isinstance(content, list):
                        for it in content:
                            if not isinstance(it, dict) or it.get("type") != "tool_use":
                                continue
                            tid = it.get("id")
                            if not tid or tid in tool_uses:
                                A["meta"]["dup_tool_use"] += 1 if tid else 0
                                continue
                            name = it.get("name") or "?"
                            inp = it.get("input") if isinstance(it.get("input"), dict) else {}
                            b, sub = ("", "")
                            if name == "Bash":
                                b, sub = bash_bin(inp.get("command"))
                                S["bash_bins"][b] += 1
                                A["bash_bins"][b] += 1
                                if b == "git" and sub == "commit":
                                    S["git_commit_calls"] += 1
                            elif name == "Skill":
                                sk = inp.get("skill")
                                if isinstance(sk, str) and len(sk) < 80:
                                    A["usage"]["skills_tool"][sk] += 1
                            elif name in ("Agent", "Task"):
                                st = inp.get("subagent_type") or "general-purpose(default)"
                                if isinstance(st, str) and len(st) < 60:
                                    A["usage"]["subagents"][st] += 1
                                mo = inp.get("model")
                                if isinstance(mo, str) and len(mo) < 20:
                                    A["usage"]["subagent_model_override"][mo] += 1
                            tool_uses[tid] = (name, f, ts, model, proj, b, sub)
                            S["tool_calls"] += 1
                            S["tools"][name] += 1
                            A["tool_calls"][name] += 1
                            if name.startswith("mcp__"):
                                srv = name.split("__")[1] if name.count("__") >= 2 else "?"
                                A["usage"]["mcp_servers"][srv] += 1
                                if ts and (srv not in A["mcp_last_seen"] or ts > A["mcp_last_seen"][srv]):
                                    A["mcp_last_seen"][srv] = ts
                                A["usage"]["mcp_tools"][name] += 1
                    if pdn is not None:
                        names = [it.get("name") for it in content if isinstance(it, dict) and it.get("type") == "tool_use"] if isinstance(content, list) else []
                        record_perm(A, pdn, names[0] if names else "?", None, (proj, f"{r.get('entrypoint')}|{S.get('pmode')}"))

                if t == "user" and m:
                    if isinstance(content, list) and any(isinstance(x, dict) and x.get("type") == "tool_result" for x in content):
                        for it in content:
                            if not isinstance(it, dict) or it.get("type") != "tool_result":
                                continue
                            tid = it.get("tool_use_id")
                            if not tid or tid in seen_results:
                                continue
                            seen_results.add(tid)
                            tu = tool_uses.get(tid)
                            name, _, _, model, tproj, b, sub = tu if tu else ("<unjoined>", f, ts, "unknown", proj, "", "")
                            if pdn is not None:
                                record_perm(A, pdn, name, (b, sub), (proj, f"{r.get('entrypoint')}|{S.get('pmode')}"))
                            iserr = it.get("is_error") is True
                            A["results"]["total"] += 1
                            if not tu:
                                A["results"]["unjoined"] += 1
                            key_t = name if not name.startswith("mcp__") else name
                            A["err_by_tool"][key_t][0] += 1
                            srv = name.split("__")[1] if name.startswith("mcp__") and name.count("__") >= 2 else None
                            if srv:
                                A["err_by_mcp"][srv][0] += 1
                            A["err_by_project"][tproj][0] += 1
                            A["err_by_model"][model][0] += 1
                            wk = week(ts) if ts else "?"
                            A["err_by_week"][wk][0] += 1
                            if not iserr:
                                prev_err = None
                                streak = 0
                                continue
                            S["tool_errors"] += 1
                            A["err_by_tool"][key_t][1] += 1
                            if srv:
                                A["err_by_mcp"][srv][1] += 1
                            A["err_by_project"][tproj][1] += 1
                            A["err_by_model"][model][1] += 1
                            A["err_by_week"][wk][1] += 1
                            raw = text_of(it.get("content"))[:3000]
                            if not raw and isinstance(r.get("toolUseResult"), str):
                                raw = r["toolUseResult"][:3000]
                            sig = signature(raw)
                            A["err_sigs"][sig] += 1
                            A["err_sig_tools"][sig][name if not srv else "mcp__" + srv] += 1
                            if sig not in A["err_sig_example"]:
                                A["err_sig_example"][sig] = f
                            low = raw.lower()
                            if "has not been read" in low or "read it first" in low:
                                A["edit_failures"]["file-not-read"] += 1
                            if "string to replace not found" in low:
                                A["edit_failures"]["string-not-found"] += 1
                            if "modified since read" in low or "has been modified" in low:
                                A["edit_failures"]["modified-since-read"] += 1
                            if "found " in low and "matches of the string" in low:
                                A["edit_failures"]["multiple-matches"] += 1
                            if any(k in low for k in ("pretooluse", "hook", "blocked")):
                                A["hook_blocks"][signature(raw, 70)] += 1
                            if "permission" in low and ("denied" in low or "rejected" in low or "not allowed" in low or "doesn't want" in low):
                                A["perm_denials_sig"][signature(raw, 70)] += 1
                            if "user doesn't want to proceed" in low or "user rejected" in low or "was rejected" in low:
                                A["user_rejections_by_tool"][name] += 1
                            for rx in CNF_RES:
                                for mm in rx.finditer(redact(raw[:1500])):
                                    A["cmd_not_found"][mm.group(1)] += 1
                            if name == "Bash" and b in BUILD_BINS:
                                for cls, rx in BUILD_CLASSES:
                                    if rx.search(raw):
                                        A["build_failures"][f"{b} {sub}".strip() + " :: " + cls] += 1
                                        break
                            if name == "Bash":
                                A["bash_err_bins"][b] += 1
                            k = (name, sig)
                            if k == prev_err:
                                streak += 1
                                if streak == 3:
                                    S["retry_loops"] += 1
                                    A["retry_loops"][f"{name} :: {sig}"[:110]] += 1
                                    A["retry_loop_example"].setdefault(f"{name} :: {sig}"[:110], f)
                            else:
                                prev_err = k
                                streak = 1
                    else:
                        if pdn is not None:
                            record_perm(A, pdn, "?", None)
                        if r.get("isMeta") or S["sidechain"] or r.get("isSidechain"):
                            continue
                        txt = text_of(content)
                        if not txt:
                            continue
                        mcmd = re.search(r"<command-name>\s*(/[A-Za-z0-9:_\-]{1,50})\s*</command-name>", txt)
                        if mcmd:
                            A["usage"]["slash_commands"][mcmd.group(1)] += 1
                            continue
                        if "[Request interrupted" in txt:
                            S["interrupts"] += 1
                            A["meta"]["interrupts"] += 1
                            S["last_user_kind"] = "interrupt"
                            continue
                        st = txt.lstrip()
                        if st.startswith(("<", "Caveat:", "[Image", "This session is being continued")):
                            continue
                        if re.match(r"^/[A-Za-z0-9:_\-]{1,50}(\s|$)", st):
                            A["usage"]["slash_commands"][st.split()[0]] += 1
                        S["user_prompts"] += 1
                        ep = (r.get("entrypoint") or "")
                        if ep == "sdk-cli":
                            continue
                        sig = norm_prompt(st)
                        low = st.lower()
                        S["last_user_sig"] = sig
                        S["last_user_kind"] = "frustration" if FRUSTRATION_RE.match(low) else "prompt"
                        if CORRECTION_RE.match(low):
                            A["corrections"][sig] += 1
                            A["correction_themes"][theme_of(low[:300])] += 1
        S.pop("_last", None)
        A["sessions"].append(S)

    # aggregate usage
    for mid, v in msg_usage.items():
        inp, c5, c1, cr, out, speed, geo, model, f, ts, proj, side, sk = v
        c = cost_usd((inp, c5, c1, cr, out, speed, geo), model)
        if c is None:
            A["meta"]["unpriced_models"][model] += 1
            c = 0.0
        tok = (inp, c5 + c1, cr, out)
        fam = family(model)
        for bucket, key in (("by_model", model), ("by_family", fam), ("by_project", proj),
                            ("by_week", week(ts) if ts else "?"), ("by_thread", "subagent" if side else "main"),
                            ("by_skill_attribution", sk or "<none>")):
            add_tok(A["cost"][bucket][key], tok, c)
        if ts and ts >= TODAY - dt.timedelta(days=30):
            add_tok(A["cost"]["last30_by_family"][fam], tok, c)
            add_tok(A["cost"]["last30_by_model"][model], tok, c)
        elif ts and ts >= TODAY - dt.timedelta(days=60):
            add_tok(A["cost"]["prev30_by_family"][fam], tok, c)
        add_tok(A["cost"]["total"]["all"], tok, c)
        A["_sess_cost"][f] = A["_sess_cost"].get(f, 0.0) + c
        st = A["_sess_tok"].setdefault(f, [0, 0, 0, 0])
        for i in range(4):
            st[i] += tok[i]

def add_tok(d, tok, c):
    d.setdefault("input", 0); d.setdefault("cache_write", 0); d.setdefault("cache_read", 0); d.setdefault("output", 0); d.setdefault("usd", 0.0); d.setdefault("msgs", 0)
    d["input"] += tok[0]; d["cache_write"] += tok[1]; d["cache_read"] += tok[2]; d["output"] += tok[3]; d["usd"] += c; d["msgs"] += 1

def record_perm(A, pdn, tool, binsub, ctx=None):
    if isinstance(pdn, dict):
        dec = str(pdn.get("decision")); src = str(pdn.get("source")); rt = str(pdn.get("reasonType"))
    else:
        dec, src, rt = str(pdn)[:20], "?", "?"
    A["perm"]["decision"][f"{dec}|{src}|{rt}"] += 1
    label = tool if not tool.startswith("mcp__") else tool
    if tool == "Bash" and binsub:
        label = f"Bash({binsub[0]} {binsub[1]})".replace(" )", ")")
    if src.startswith("user"):
        A["perm"]["user_" + dec][label] += 1
    if rt == "classifier":
        A["perm"]["classifier_" + dec][label] += 1
    if dec == "reject":
        A["perm"]["reject_by_tool"][label] += 1
        if ctx:
            A["perm"]["reject_by_project"][ctx[0]] += 1
            A["perm"]["reject_by_entrypoint_mode"][ctx[1]] += 1

# ---------------------------------------------------------------- Codex
def mine_codex(root, A):
    files = sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True))
    A["meta"]["codex_files"] = len(files)
    seen_resp = set()
    for f in files:
        S = new_session(f, "codex")
        model = "unknown"
        try:
            fh = open(f, "r", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                A["meta"]["codex_lines"] += 1
                try:
                    r = json.loads(line)
                except Exception:
                    A["meta"]["codex_bad_json"] += 1
                    continue
                if not isinstance(r, dict):
                    continue
                t = r.get("type"); p = r.get("payload") if isinstance(r.get("payload"), dict) else {}
                ts = parse_ts(r.get("timestamp"))
                touch(S, ts)
                if t == "session_meta":
                    if isinstance(p.get("cwd"), str):
                        S["cwd"][p["cwd"]] += 1
                    o = p.get("originator")
                    if isinstance(o, str) and len(o) < 40:
                        S["entrypoint"][o] += 1
                    if p.get("thread_source") or p.get("source") == "subagent":
                        pass
                elif t == "turn_context":
                    if isinstance(p.get("model"), str) and len(p["model"]) < 40:
                        model = p["model"]
                    ap = p.get("approval_policy")
                    if isinstance(ap, str):
                        A["codex"]["approval_policy"][ap] += 1
                    sp = p.get("sandbox_policy")
                    if isinstance(sp, dict) and isinstance(sp.get("type"), str):
                        A["codex"]["sandbox_policy"][sp["type"]] += 1
                    if isinstance(p.get("cwd"), str):
                        S["cwd"][p["cwd"]] += 1
                elif t == "compacted":
                    S["compactions"] += 1
                elif t == "token_usage_record":
                    rid = p.get("response_id")
                    if rid in seen_resp:
                        continue
                    seen_resp.add(rid)
                    u = p.get("usage") if isinstance(p.get("usage"), dict) else {}
                    S["models"][model] += 1
                    d = A["codex"]["tokens_by_model"].setdefault(model, {"input": 0, "cached_input": 0, "cache_write": 0, "output": 0, "reasoning_output": 0, "responses": 0})
                    d["input"] += u.get("input_tokens") or 0; d["cached_input"] += u.get("cached_input_tokens") or 0
                    d["cache_write"] += u.get("cache_write_input_tokens") or 0; d["output"] += u.get("output_tokens") or 0
                    d["reasoning_output"] += u.get("reasoning_output_tokens") or 0; d["responses"] += 1
                    if ts:
                        A["codex"]["responses_by_week"][week(ts)] += 1
                elif t == "event_msg" and p.get("type") == "item_completed":
                    it = p.get("item") if isinstance(p.get("item"), dict) else {}
                    ity = it.get("type")
                    A["codex"]["items"][str(ity)] += 1
                    if ity == "CommandExecution":
                        S["tool_calls"] += 1
                        cmd = it.get("command")
                        if isinstance(cmd, list):
                            cmd = cmd[-1] if cmd and cmd[0] in ("bash", "zsh", "sh", "/bin/zsh", "/bin/bash") else " ".join(map(str, cmd))
                        b, sub = bash_bin(cmd if isinstance(cmd, str) else "")
                        if b in ("bash", "zsh", "sh") and isinstance(cmd, str):
                            mm = re.search(r"-l?c\s+['\"]?(.*)", cmd)
                            if mm:
                                b, sub = bash_bin(mm.group(1))
                        A["codex"]["cmd_bins"][b] += 1
                        ec = it.get("exit_code")
                        if (isinstance(ec, int) and ec != 0) or it.get("status") == "failed":
                            S["tool_errors"] += 1
                            A["codex"]["cmd_fail_bins"][b] += 1
                            raw = it.get("aggregated_output") if isinstance(it.get("aggregated_output"), str) else ""
                            for rx in CNF_RES:
                                for mm in rx.finditer(redact(raw[-1500:])):
                                    A["codex"]["cmd_not_found"][mm.group(1)] += 1
                            if "sandbox" in raw.lower() or "operation not permitted" in raw.lower():
                                A["codex"]["sandbox_denials"][b] += 1
                    elif ity == "McpToolCall":
                        S["tool_calls"] += 1
                        srv = it.get("server") if isinstance(it.get("server"), str) else "?"
                        A["codex"]["mcp_servers"][srv] += 1
                        if it.get("status") not in ("completed", None):
                            A["codex"]["mcp_fail_servers"][srv] += 1
                    elif ity == "WebSearch":
                        S["tool_calls"] += 1
                    elif ity == "SubAgentActivity":
                        A["codex"]["subagent_activity"] += 1
                    elif ity == "UserMessage":
                        S["user_prompts"] += 1
        S.pop("_last", None)
        A["sessions"].append(S)

# ---------------------------------------------------------------- git correlation (read-only)
def git_commits(cwd, start, end):
    if not cwd:
        return None
    m = re.match(r"(.*?)/\.claude/worktrees/", cwd)
    if m:
        cwd = m.group(1)
    while cwd and cwd != "/" and not os.path.isdir(cwd):
        cwd = os.path.dirname(cwd)
    if not cwd or cwd in ("/", HOME):
        return None
    try:
        top = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
        if top.returncode != 0:
            return None
        rt = top.stdout.strip()
        lg = subprocess.run(["git", "-C", rt, "log", "--all", f"--since={start.isoformat()}",
                             f"--until={(end + dt.timedelta(minutes=30)).isoformat()}", "--format=%H"],
                            capture_output=True, text=True, timeout=20)
        return len([x for x in lg.stdout.split() if x]) if lg.returncode == 0 else None
    except Exception:
        return None

# ---------------------------------------------------------------- report
def finalize(A, do_git):
    out = {"meta": dict(A["meta"]), "prices_usd_per_mtok": {k: dict(zip(["input", "cache_write_5m", "cache_write_1h", "cache_read", "output"], v)) for k, v in PRICES},
           "price_notes": "Haiku 5.5 >100K-token prompts use 0.5/0.625/1/0.05/2.5; fast mode Opus 5.5 8/40 (cache multipliers on top); inference_geo=us x1.1. Source platform.claude.com/docs/en/about-claude/pricing fetched 2026-10-19. API-equivalent list prices, not subscription billing."}
    out["meta"]["unpriced_models"] = dict(A["meta"]["unpriced_models"])

    def rate_table(d, minn=1):
        rows = [{"key": k, "calls": v[0], "errors": v[1], "error_rate": round(v[1] / v[0], 4) if v[0] else 0} for k, v in d.items() if v[0] >= minn]
        return sorted(rows, key=lambda x: (-x["errors"], -x["calls"]))

    rel = {"results": dict(A["results"]),
           "by_tool": rate_table(A["err_by_tool"])[:60], "by_mcp_server": rate_table(A["err_by_mcp"]),
           "by_project": rate_table(A["err_by_project"])[:40], "by_model": rate_table(A["err_by_model"]),
           "by_week": sorted(rate_table(A["err_by_week"]), key=lambda x: x["key"]),
           "top_error_signatures": [{"sig": s, "count": n, "tools": dict(A["err_sig_tools"][s].most_common(4)), "example_session": A["err_sig_example"].get(s)} for s, n in A["err_sigs"].most_common(25)],
           "edit_failures": dict(A["edit_failures"]), "cmd_not_found": dict(A["cmd_not_found"].most_common(30)),
           "build_failures": dict(A["build_failures"].most_common(40)), "bash_err_bins": dict(A["bash_err_bins"].most_common(30)),
           "hook_blocks": dict(A["hook_blocks"].most_common(20)), "hooks": dict(A["hooks"]), "hook_errors_by_hook": dict(A["hook_errors_by_hook"].most_common(20)),
           "perm_denial_sigs": dict(A["perm_denials_sig"].most_common(20)), "user_rejections_by_tool": dict(A["user_rejections_by_tool"].most_common(20)),
           "permission_decisions": {k: dict(v.most_common(40)) for k, v in A["perm"].items()},
           "retry_loops": [{"pattern": k, "count": v, "example_session": A["retry_loop_example"].get(k)} for k, v in A["retry_loops"].most_common(25)],
           "api_errors": dict(A["api_errors"].most_common(15)), "system_subtypes": dict(A["system_subtypes"])}
    out["reliability"] = rel

    # sessions
    sess = A["sessions"]
    for S in sess:
        S["cwd_top"] = S["cwd"].most_common(1)[0][0] if S["cwd"] else ""
        S["project"] = project_of(S["cwd_top"])
        S["usd"] = round(A["_sess_cost"].get(S["path"], 0.0), 4)
        S["tokens"] = A["_sess_tok"].get(S["path"], [0, 0, 0, 0])
        S["duration_h"] = round((S["end"] - S["start"]).total_seconds() / 3600, 2) if S["start"] and S["end"] else 0
        S["active_h"] = round(S["active_s"] / 3600, 2)
        S["model_top"] = S["models"].most_common(1)[0][0] if S["models"] else ""
        S["ep_top"] = S["entrypoint"].most_common(1)[0][0] if S["entrypoint"] else ""
    cl = [s for s in sess if s["client"] == "claude"]
    cx = [s for s in sess if s["client"] == "codex"]

    # roll up subagent files into their parent session id
    roll = {}
    for s in cl:
        key = s["session_id"] or s["path"]
        R = roll.setdefault(key, {"session_id": key, "paths": [], "main_path": None, "usd": 0.0, "tokens": [0, 0, 0, 0], "tool_calls": 0, "tool_errors": 0,
                                  "subagent_files": 0, "subagent_usd": 0.0, "models": C(), "project": None, "start": None, "end": None, "active_h": 0.0, "compactions": 0, "retry_loops": 0})
        R["paths"].append(s["path"]); R["usd"] += s["usd"]; R["tool_calls"] += s["tool_calls"]; R["tool_errors"] += s["tool_errors"]
        R["compactions"] += s["compactions"]; R["retry_loops"] += s["retry_loops"]
        for i in range(4):
            R["tokens"][i] += s["tokens"][i]
        R["models"].update(s["models"])
        if s["sidechain"]:
            R["subagent_files"] += 1; R["subagent_usd"] += s["usd"]
        else:
            R["main_path"] = R["main_path"] or s["path"]; R["project"] = s["project"]; R["active_h"] += s["active_h"]
        for k in ("start", "end"):
            if s[k] and (R[k] is None or (s[k] < R[k] if k == "start" else s[k] > R[k])):
                R[k] = s[k]
    def why(R):
        t = R["tokens"]; tot = sum(t) or 1
        reasons = []
        if t[2] / tot > 0.9:
            reasons.append(f"long context re-read: cache_read {t[2]/1e6:.0f}M tok ({t[2]/tot:.0%})")
        if t[1] > 5e6:
            reasons.append(f"heavy cache_write {t[1]/1e6:.1f}M")
        if R["tool_calls"] > 300:
            reasons.append(f"{R['tool_calls']} tool calls")
        if R["tool_calls"] and R["tool_errors"] / R["tool_calls"] > 0.1:
            reasons.append(f"{R['tool_errors']} tool errors ({R['tool_errors']/R['tool_calls']:.0%})")
        if R["subagent_files"]:
            reasons.append(f"{R['subagent_files']} subagent files ${R['subagent_usd']:.0f}")
        if R["compactions"]:
            reasons.append(f"{R['compactions']} compactions")
        return "; ".join(reasons) or "steady long session"
    top = sorted(roll.values(), key=lambda R: -R["usd"])[:10]
    out["cost"] = {k: ({kk: round_d(vv) for kk, vv in v.items()} if isinstance(v, dict) else v) for k, v in A["cost"].items()}
    tot = A["cost"]["total"]["all"]
    denom = tot.get("input", 0) + tot.get("cache_write", 0) + tot.get("cache_read", 0)
    out["cost"]["cache_hit_rate"] = round(tot.get("cache_read", 0) / denom, 4) if denom else None
    for fam, d in A["cost"]["by_family"].items():
        dn = d["input"] + d["cache_write"] + d["cache_read"]
        out["cost"]["by_family"][fam]["cache_hit_rate"] = round(d["cache_read"] / dn, 4) if dn else None
    l30 = A["cost"]["last30_by_family"]
    dn = sum(d["input"] + d["cache_write"] + d["cache_read"] for d in l30.values())
    out["cost"]["last30_cache_hit_rate"] = round(sum(d["cache_read"] for d in l30.values()) / dn, 4) if dn else None
    out["cost"]["cost_state_crosscheck_usd"] = round(sum(s["cost_state_usd"] or 0 for s in cl), 2)
    out["cost"]["top10_sessions"] = [{"session_id": R["session_id"], "main_path": R["main_path"] or R["paths"][0], "project": R["project"],
                                      "model": R["models"].most_common(1)[0][0] if R["models"] else "", "usd": round(R["usd"], 2),
                                      "tokens": dict(zip(["input", "cache_write", "cache_read", "output"], R["tokens"])),
                                      "wall_h": round((R["end"] - R["start"]).total_seconds() / 3600, 1) if R["start"] and R["end"] else None,
                                      "active_h": round(R["active_h"], 1), "tool_calls": R["tool_calls"], "tool_errors": R["tool_errors"],
                                      "subagent_files": R["subagent_files"], "subagent_usd": round(R["subagent_usd"], 2), "why": why(R)} for R in top]
    # mechanical work on top-tier models
    MECH = {"Bash", "Read", "Grep", "Glob", "LS"}
    mech = []
    for s in cl:
        fam = family(s["model_top"])
        if fam not in ("fable", "opus") or s["tool_calls"] < 20:
            continue
        mcount = sum(v for k, v in s["tools"].items() if k in MECH)
        edits = sum(v for k, v in s["tools"].items() if k in ("Edit", "Write", "MultiEdit", "NotebookEdit"))
        outp = s["tokens"][3] / max(s["assistant_msgs"], 1)
        if mcount / s["tool_calls"] > 0.8 and edits <= 2 and outp < 400:
            mech.append({"path": s["path"], "project": s["project"], "model": s["model_top"], "sidechain": s["sidechain"], "tool_calls": s["tool_calls"],
                         "mechanical_share": round(mcount / s["tool_calls"], 2), "edits": edits, "out_tok_per_msg": round(outp), "usd": s["usd"]})
    mech.sort(key=lambda x: -x["usd"])
    def sonnet_equiv(x):
        return x["usd"] * 0.5 if "opus-5-5" in x["model"] else x["usd"] * 0.2
    out["cost"]["mechanical_on_top_tier"] = {"count": len(mech), "usd": round(sum(x["usd"] for x in mech), 2),
                                             "usd_if_sonnet_5_5_est": round(sum(sonnet_equiv(x) for x in mech), 2),
                                             "by_family": dict(C(family(x["model"]) for x in mech)), "fable_count": sum(1 for x in mech if "fable" in x["model"]),
                                             "top": mech[:15]}

    # effort and waste
    long_s = [s for s in cl if not s["sidechain"] and (s["active_h"] > 2 or s["tool_calls"] > 300)]
    long_rows = []
    for s in sorted(long_s, key=lambda s: -s["usd"]):
        commits = git_commits(s["cwd_top"], s["start"], s["end"]) if do_git and s["start"] else None
        long_rows.append({"path": s["path"], "project": s["project"], "active_h": s["active_h"], "wall_h": s["duration_h"], "tool_calls": s["tool_calls"],
                          "usd": s["usd"], "git_commit_calls": s["git_commit_calls"], "git_log_commits_in_window": commits})
    no_commit = [x for x in long_rows if x["git_commit_calls"] == 0 and (x["git_log_commits_in_window"] in (0,))]
    no_repo = [x for x in long_rows if x["git_commit_calls"] == 0 and x["git_log_commits_in_window"] is None]
    out["effort"] = {
        "claude_sessions": len(cl), "claude_main_sessions": sum(1 for s in cl if not s["sidechain"]), "claude_subagent_files": sum(1 for s in cl if s["sidechain"]),
        "sessions_with_compaction": sum(1 for s in cl if s["compactions"]), "compaction_events": sum(s["compactions"] for s in cl),
        "compaction_top": [{"path": s["path"], "project": s["project"], "compactions": s["compactions"], "usd": s["usd"]} for s in sorted(cl, key=lambda s: -s["compactions"])[:10] if s["compactions"]],
        "long_sessions": len(long_rows), "long_sessions_no_commit": len(no_commit), "long_sessions_no_git_repo": len(no_repo),
        "long_no_commit_usd": round(sum(x["usd"] for x in no_commit), 2), "long_no_repo_usd": round(sum(x["usd"] for x in no_repo), 2),
        "long_no_commit_top": sorted(no_commit, key=lambda x: -x["usd"])[:12], "long_with_commit": sum(1 for x in long_rows if x["git_commit_calls"] or x["git_log_commits_in_window"]), "long_no_repo_top": sorted(no_repo, key=lambda x: -x["usd"])[:8],
        "sessions_with_interrupts": sum(1 for s in cl if s["interrupts"]), "interrupts_total": sum(s["interrupts"] for s in cl),
        "sessions_ending_interrupt": sum(1 for s in cl if s["last_user_kind"] == "interrupt"),
        "sessions_ending_frustration": sum(1 for s in cl if s["last_user_kind"] == "frustration"),
        "ending_frustration_examples": [s["path"] for s in cl if s["last_user_kind"] == "frustration"][:8],
        "corrections_min3": {k: v for k, v in A["corrections"].most_common(60) if v >= 3},
        "corrections_total": sum(A["corrections"].values()), "correction_themes": dict(A["correction_themes"].most_common()),
        "retry_loop_sessions": sum(1 for s in cl if s["retry_loops"]),
    }

    # usage
    def lastn(sl, a, b):
        return sum(1 for s in sl if s["start"] and TODAY - dt.timedelta(days=b) <= s["start"] < TODAY - dt.timedelta(days=a))
    spw = C(week(s["start"]) for s in sess if s["start"] and not s["sidechain"])
    spw_c = C(week(s["start"]) for s in cx if s["start"])
    out["usage"] = {k: dict(v.most_common(80)) for k, v in A["usage"].items()}
    out["usage"]["tool_calls"] = dict(A["tool_calls"].most_common(60))
    out["usage"]["bash_bins"] = dict(A["bash_bins"].most_common(40))
    out["usage"]["skill_attribution_msgs"] = {k: v["msgs"] for k, v in A["cost"]["by_skill_attribution"].items()}
    out["usage"]["sessions_per_week_claude_main"] = dict(sorted((k, v) for k, v in spw.items() if k not in spw_c or True))
    out["usage"]["sessions_per_week_codex"] = dict(sorted(spw_c.items()))
    cm = [s for s in cl if not s["sidechain"]]
    out["usage"]["claude_main_sessions_last30_vs_prev30"] = [lastn(cm, 0, 30), lastn(cm, 30, 60)]
    out["usage"]["codex_sessions_last30_vs_prev30"] = [lastn(cx, 0, 30), lastn(cx, 30, 60)]
    out["usage"]["client_share"] = {"claude_main_sessions": len(cm), "codex_sessions": len(cx), "cursor": "no local transcript store parsed",
                                    "claude_tool_calls": sum(s["tool_calls"] for s in cl), "codex_tool_calls": sum(s["tool_calls"] for s in cx)}
    out["usage"]["entrypoints"] = dict(C(s["ep_top"] for s in cl))
    epc = DD(lambda: {"files": 0, "usd": 0.0, "tool_calls": 0, "tool_errors": 0})
    for s in cl:
        e = epc[s["ep_top"] or "?"]; e["files"] += 1; e["usd"] = round(e["usd"] + s["usd"], 2); e["tool_calls"] += s["tool_calls"]; e["tool_errors"] += s["tool_errors"]
    out["usage"]["by_entrypoint"] = dict(epc)
    pc = DD(lambda: {"files": 0, "usd": 0.0})
    for s in cl:
        if s["ep_top"] == "sdk-cli":
            e = pc[s["project"]]; e["files"] += 1; e["usd"] = round(e["usd"] + s["usd"], 2)
    out["usage"]["sdk_cli_by_project"] = dict(sorted(pc.items(), key=lambda x: -x[1]["usd"]))
    out["usage"]["mcp_server_last_seen"] = {k: v.isoformat()[:10] for k, v in sorted(A["mcp_last_seen"].items())}
    # never-used
    used_sk = set(out["usage"].get("skills_tool", {})) | set(k for k in out["usage"]["skill_attribution_msgs"] if k != "<none>") | {k.lstrip("/") for k in out["usage"].get("slash_commands", {})}
    used_sk_base = {k.split(":")[-1] for k in used_sk}
    inst = A["installed"]
    out["usage"]["never_used_skills"] = sorted(s for s in inst.get("skills", []) if s not in used_sk_base and s not in used_sk)
    out["usage"]["installed_skill_count"] = len(inst.get("skills", []))
    used_srv = set(out["usage"].get("mcp_servers", {})) | set(A["codex"]["mcp_servers"])
    out["usage"]["never_used_mcp_servers"] = sorted(s for s in inst.get("mcp_servers", []) if s not in used_srv)
    out["usage"]["never_used_agents"] = sorted(a for a in inst.get("agents", []) if a not in out["usage"].get("subagents", {}))
    out["codex"] = {k: (dict(v.most_common(40)) if isinstance(v, collections.Counter) else v) for k, v in A["codex"].items()}
    out["codex"]["sessions"] = len(cx)
    out["codex"]["sessions_with_compaction"] = sum(1 for s in cx if s["compactions"])
    out["codex"]["cmd_error_rate"] = round(sum(s["tool_errors"] for s in cx) / max(sum(s["tool_calls"] for s in cx), 1), 4)
    return out

def round_d(v):
    if isinstance(v, dict):
        return {k: (round(x, 2) if isinstance(x, float) else x) for k, x in v.items()}
    return v

def new_acc():
    A = {"meta": C(), "results": C(), "err_by_tool": DD(lambda: [0, 0]), "err_by_mcp": DD(lambda: [0, 0]), "err_by_project": DD(lambda: [0, 0]),
         "err_by_model": DD(lambda: [0, 0]), "err_by_week": DD(lambda: [0, 0]), "err_sigs": C(), "err_sig_tools": DD(C), "err_sig_example": {},
         "edit_failures": C(), "cmd_not_found": C(), "build_failures": C(), "bash_err_bins": C(), "hook_blocks": C(), "hooks": C(),
         "hook_errors_by_hook": C(), "perm_denials_sig": C(), "user_rejections_by_tool": C(), "perm": DD(C), "retry_loops": C(), "retry_loop_example": {},
         "api_errors": C(), "system_subtypes": C(), "usage_flags": C(), "perm_modes": C(), "hook_error_keys": C(), "hook_error_sigs": C(), "hook_error_days": C(), "mcp_last_seen": {}, "tool_calls": C(), "bash_bins": C(),
         "usage": {"skills_tool": C(), "subagents": C(), "subagent_model_override": C(), "mcp_servers": C(), "mcp_tools": C(), "slash_commands": C()},
         "corrections": C(), "correction_themes": C(), "sessions": [], "_sess_cost": {}, "_sess_tok": {},
         "cost": {k: DD(dict) for k in ("by_model", "by_family", "by_project", "by_week", "by_thread", "by_skill_attribution", "last30_by_family", "last30_by_model", "prev30_by_family", "total")},
         "codex": {"approval_policy": C(), "sandbox_policy": C(), "tokens_by_model": {}, "responses_by_week": C(), "items": C(), "cmd_bins": C(), "cmd_fail_bins": C(),
                   "cmd_not_found": C(), "sandbox_denials": C(), "mcp_servers": C(), "mcp_fail_servers": C(), "subagent_activity": 0},
         "installed": {}}
    A["meta"]["unpriced_models"] = C()
    return A

def installed_inventory():
    inv = {"skills": [], "mcp_servers": [], "agents": []}
    names = set()
    for d in (HOME + "/.agents/skills", HOME + "/.claude/skills"):
        if os.path.isdir(d):
            for n in os.listdir(d):
                if not n.startswith(".") and os.path.exists(os.path.join(d, n, "SKILL.md")):
                    names.add(n)
    inv["skills"] = sorted(names)
    bl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baseline.json")
    try:
        b = json.load(open(bl))
        inv["mcp_servers"] = b["mcp_list_status"]["user_servers"]
    except Exception:
        pass
    ad = HOME + "/.claude/agents"
    if os.path.isdir(ad):
        inv["agents"] = sorted(n[:-3] for n in os.listdir(ad) if n.endswith(".md"))
    return inv

def run(claude_root, codex_root, out_path, do_git, installed=None):
    A = new_acc()
    A["installed"] = installed if installed is not None else installed_inventory()
    mine_claude(claude_root, A)
    if codex_root and os.path.isdir(codex_root):
        mine_codex(codex_root, A)
    out = finalize(A, do_git)
    out["usage_flags"] = dict(A["usage_flags"])
    out["reliability"]["permission_mode_records"] = dict(A["perm_modes"])
    out["reliability"]["hook_error_keys"] = dict(A["hook_error_keys"])
    out["reliability"]["hook_error_sigs"] = dict(A["hook_error_sigs"].most_common(15))
    out["reliability"]["hook_error_days"] = dict(sorted(A["hook_error_days"].items()))
    out["effort"]["user_prompts_total"] = sum(s["user_prompts"] for s in A["sessions"] if s["client"] == "claude")
    s = json.dumps(out, indent=1, default=str)
    with open(out_path, "w") as fh:
        fh.write(s)
    return out, s

# ---------------------------------------------------------------- self-test
def selftest():
    tmp = tempfile.mkdtemp(prefix="mine-selftest-")
    cr = os.path.join(tmp, "claude", "-Users-x-Projects-Demo"); os.makedirs(os.path.join(cr, "sess1", "subagents"))
    xr = os.path.join(tmp, "codex", "2026", "10", "01"); os.makedirs(xr)
    SECRET = "sk-ant-api03-SELFTESTSECRETVALUE1234567890abcdef"
    PRIVATE = "PRIVATE_PROMPT_TEXT_SHOULD_NOT_LEAK"
    base = {"sessionId": "sess1", "cwd": "/Users/x/Projects/Demo", "isSidechain": False, "entrypoint": "claude-desktop", "version": "2"}
    def ts(m): return f"2026-10-10T10:{m:02d}:00Z"
    recs = [
        dict(base, type="user", timestamp=ts(0), message={"role": "user", "content": "no, use bun not npm " + PRIVATE}),
        dict(base, type="user", timestamp=ts(1), message={"role": "user", "content": "<command-name>/ship</command-name>"}),
        dict(base, type="assistant", timestamp=ts(2), message={"id": "m1", "model": "claude-opus-5-5", "role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": f"FOO=1 wrangler deploy --token {SECRET}"}}],
            "usage": {"input_tokens": 1000, "output_tokens": 10, "cache_creation_input_tokens": 2000, "cache_read_input_tokens": 100000, "cache_creation": {"ephemeral_1h_input_tokens": 0}}}),
        dict(base, type="assistant", timestamp=ts(2), message={"id": "m1", "model": "claude-opus-5-5", "role": "assistant", "content": [{"type": "text", "text": PRIVATE}],
            "usage": {"input_tokens": 1000, "output_tokens": 500, "cache_creation_input_tokens": 2000, "cache_read_input_tokens": 100000}}),
        dict(base, type="user", timestamp=ts(3), permissionDecision={"decision": "accept", "source": "user_temporary", "reasonType": "rule"},
             message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": f"zsh: command not found: wrangler\nauth {SECRET}"}]}),
    ]
    for i in range(3):
        recs.append(dict(base, type="assistant", timestamp=ts(4 + 2 * i), message={"id": f"e{i}", "model": "claude-fable-5-1", "role": "assistant",
                    "content": [{"type": "tool_use", "id": f"te{i}", "name": "Edit", "input": {"file_path": "/a/b", "old_string": PRIVATE}}], "usage": {"input_tokens": 10, "output_tokens": 10}}))
        recs.append(dict(base, type="user", timestamp=ts(5 + 2 * i), message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"te{i}", "is_error": True,
                    "content": "<tool_use_error>String to replace not found in file.\nString: " + PRIVATE + "</tool_use_error>"}]}))
    recs.append(dict(base, type="system", subtype="compact_boundary", timestamp=ts(20)))
    recs.append(dict(base, type="user", timestamp=ts(21), message={"role": "user", "content": [{"type": "text", "text": "[Request interrupted by user]"}]}))
    with open(os.path.join(cr, "sess1.jsonl"), "w") as fh:
        for r in recs: fh.write(json.dumps(r) + "\n")
        fh.write("{not json\n")
    sub = [dict(base, isSidechain=True, type="assistant", timestamp=ts(30), message={"id": "s1", "model": "claude-haiku-5-5", "role": "assistant", "content": [
        {"type": "tool_use", "id": "ts1", "name": "mcp__stacks__search", "input": {"q": PRIVATE}}], "usage": {"input_tokens": 200000, "output_tokens": 100}})]
    with open(os.path.join(cr, "sess1", "subagents", "agent-a.jsonl"), "w") as fh:
        for r in sub: fh.write(json.dumps(r) + "\n")
    cx = [{"timestamp": ts(0), "type": "session_meta", "payload": {"cwd": "/Users/x/Projects/Demo", "originator": "codex_exec"}},
          {"timestamp": ts(1), "type": "turn_context", "payload": {"model": "gpt-6-luna", "approval_policy": "never", "sandbox_policy": {"type": "workspace-write"}}},
          {"timestamp": ts(2), "type": "token_usage_record", "payload": {"response_id": "r1", "usage": {"input_tokens": 50, "cached_input_tokens": 40, "output_tokens": 5}}},
          {"timestamp": ts(3), "type": "event_msg", "payload": {"type": "item_completed", "item": {"type": "CommandExecution", "command": ["bash", "-lc", "npm run build " + SECRET], "exit_code": 127, "status": "failed", "aggregated_output": "bash: npm: command not found " + PRIVATE}}}]
    with open(os.path.join(xr, "rollout.jsonl"), "w") as fh:
        for r in cx: fh.write(json.dumps(r) + "\n")
    outp = os.path.join(tmp, "out.json")
    out, s = run(os.path.join(tmp, "claude"), os.path.join(tmp, "codex"), outp, False, installed={"skills": ["ship", "unused-skill"], "mcp_servers": ["stacks", "idle"], "agents": ["x"]})
    checks = {
        "no_secret_in_output": SECRET not in s and "SELFTESTSECRET" not in s,
        "no_private_text": PRIVATE not in s,
        "dedupe_usage_max": out["cost"]["by_model"]["claude-opus-5-5"]["output"] == 500 and out["cost"]["by_model"]["claude-opus-5-5"]["msgs"] == 1,
        "opus_cost": abs(out["cost"]["by_model"]["claude-opus-5-5"]["usd"] - round((1000 * 4 + 2000 * 5 + 100000 * 0.2 + 500 * 20) / 1e6, 2)) < 0.011,
        "haiku_long_tier": out["cost"]["by_model"]["claude-haiku-5-5"]["usd"] == round((200000 * 0.5 + 100 * 2.5) / 1e6, 2),
        "cmd_not_found": out["reliability"]["cmd_not_found"].get("wrangler") == 1,
        "bash_bin": out["usage"]["bash_bins"].get("wrangler") == 1,
        "edit_string_not_found": out["reliability"]["edit_failures"].get("string-not-found") == 3,
        "retry_loop": len(out["reliability"]["retry_loops"]) == 1,
        "slash": out["usage"]["slash_commands"].get("/ship") == 1,
        "correction": sum(out["effort"]["correction_themes"].values()) == 1,
        "compaction": out["effort"]["sessions_with_compaction"] == 1,
        "interrupt_end": out["effort"]["sessions_ending_interrupt"] == 1,
        "subagent_split": "subagent" in out["cost"]["by_thread"] and "main" in out["cost"]["by_thread"],
        "perm_user_accept": out["reliability"]["permission_decisions"]["user_accept"].get("Bash(wrangler deploy)") == 1,
        "mcp_usage": out["usage"]["mcp_servers"].get("stacks") == 1,
        "never_used": out["usage"]["never_used_skills"] == ["unused-skill"] and out["usage"]["never_used_mcp_servers"] == ["idle"],
        "codex_tokens": out["codex"]["tokens_by_model"]["gpt-6-luna"]["input"] == 50,
        "codex_cnf": out["codex"]["cmd_not_found"].get("npm") == 1 and out["codex"]["cmd_fail_bins"].get("npm") == 1,
        "bad_json_counted": out["meta"]["bad_json"] == 1,
        "signature_redacts": "<redacted>" in signature("Bearer abcdefghijklmnop123 fail") and "#" in signature("line 42 failed"),
    }
    bad = [k for k, v in checks.items() if not v]
    print(json.dumps({"selftest": "PASS" if not bad else "FAIL", "failed": bad, "checks": len(checks)}))
    return 0 if not bad else 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--git", action="store_true", help="read-only git log correlation for long sessions")
    ap.add_argument("--claude-root", default=HOME + "/.claude/projects")
    ap.add_argument("--codex-root", default=HOME + "/.codex/sessions")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "mine-output.json"))
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    out, _ = run(a.claude_root, a.codex_root, a.out, a.git)
    print(json.dumps({"written": a.out, "claude_files": out["meta"].get("claude_files"), "codex_files": out["meta"].get("codex_files"),
                      "total_usd": out["cost"]["total"]["all"].get("usd")}))

if __name__ == "__main__":
    main()
