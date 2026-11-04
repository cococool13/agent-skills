#!/usr/bin/env python3
"""stackctl prototype (audit 2026-10-19). Python 3.11+ stdlib only.

Commands
  check  [--manifest F] [--home DIR] [--quiet]   read-only drift report, exit 1 on drift
  render --dry-run [--manifest F] [--home DIR]   print projected diffs per client, write nothing
  --selftest                                     run on a synthetic fixture in a temp dir

Safety: live files are read, projected to names/shapes, and only projections are
printed or diffed. No value of env, headers, args longer than 40 chars, or TOML
strings is ever printed. The prototype never writes outside --selftest's temp dir.
Production stackctl should load YAML with a pinned PyYAML and validate with a pinned
jsonschema; the loader below covers the strict subset used by stack.yaml.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
import tomllib
from pathlib import Path

SECRET_RE = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._\-]{16,}|(sk|pk|rk|ghp|gho|xox[abp]|AKIA|AIza)[A-Za-z0-9_\-]{16,}|^(?=.*[0-9])[A-Za-z0-9+/=]{40,}$)"
)
ENV_REF_RE = re.compile(r"\$\{(env:)?[A-Z][A-Z0-9_]+(:-[^}]*)?\}")
CLIENT_FILES = {
    "claude_cli": ("~/.claude.json", "mcpServers", "json"),
    "cursor": ("~/.cursor/mcp.json", "mcpServers", "json"),
    "claude_desktop": ("~/Library/Application Support/Claude/claude_desktop_config.json", "mcpServers", "json"),
    "codex": ("~/.codex/config.toml", "mcp_servers", "toml"),
    "grok": ("~/.grok/config.toml", "mcp_servers", "toml"),
}


# ---------------------------------------------------------------- YAML subset loader
def _strip_comment(line: str) -> str:
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and (i == 0 or line[i - 1] == " "):
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _scalar(tok: str):
    tok = tok.strip()
    if tok == "" or tok == "null" or tok == "~":
        return None
    if tok in ("true", "false"):
        return tok == "true"
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
        return tok[1:-1]
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    return tok


def _parse_flow(s: str, i: int = 0):
    """Parse a flow collection or scalar starting at s[i]; return (value, next_i)."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return None, i
    if s[i] == "[":
        items, i = [], i + 1
        while True:
            while i < len(s) and s[i] in " ,":
                i += 1
            if s[i] == "]":
                return items, i + 1
            v, i = _parse_flow(s, i)
            items.append(v)
    if s[i] == "{":
        d, i = {}, i + 1
        while True:
            while i < len(s) and s[i] in " ,":
                i += 1
            if s[i] == "}":
                return d, i + 1
            j = s.index(":", i)
            key = _scalar(s[i:j])
            v, i = _parse_flow(s, j + 1)
            d[key] = v
    if s[i] in "\"'":
        q = s[i]
        j = s.index(q, i + 1)
        return s[i + 1 : j], j + 1
    j = i
    while j < len(s) and s[j] not in ",]}":
        j += 1
    return _scalar(s[i:j]), j


def _value(text: str):
    text = text.strip()
    if text.startswith(("[", "{")):
        v, _ = _parse_flow(text)
        return v
    return _scalar(text)


def _split_kv(text: str):
    m = re.match(r'^("[^"]*"|\'[^\']*\'|[^:\s][^:]*?):(?:\s+(.*))?$', text)
    if not m:
        return None
    return _scalar(m.group(1)), (m.group(2) or "")


def load_yaml(text: str):
    lines = []
    for raw in text.splitlines():
        body = _strip_comment(raw)
        if body.strip():
            lines.append((len(body) - len(body.lstrip(" ")), body.strip()))

    def parse(i: int, indent: int):
        if i >= len(lines) or lines[i][0] < indent:
            return None, i
        if lines[i][1].startswith("- ") or lines[i][1] == "-":
            out = []
            while i < len(lines) and lines[i][0] == indent and (lines[i][1].startswith("- ") or lines[i][1] == "-"):
                rest = lines[i][1][2:].strip()
                kv = None if rest.startswith(("[", "{", "\"", "'")) else _split_kv(rest)
                if kv:
                    k, v = kv
                    lines[i] = (indent + 2, rest)
                    item, i = parse(i, indent + 2)
                    out.append(item)
                else:
                    out.append(_value(rest))
                    i += 1
            return out, i
        out = {}
        while i < len(lines) and lines[i][0] == indent:
            kv = _split_kv(lines[i][1])
            if not kv:
                raise ValueError(f"line {i}: cannot parse {lines[i][1]!r}")
            k, v = kv
            if v == "":
                if i + 1 < len(lines) and lines[i + 1][0] > indent:
                    out[k], i = parse(i + 1, lines[i + 1][0])
                else:
                    out[k] = None
                    i += 1
            else:
                out[k] = _value(v)
                i += 1
        return out, i

    doc, _ = parse(0, 0)
    return doc


# ---------------------------------------------------------------- validation (structural)
def validate(m: dict) -> list[str]:
    errs: list[str] = []
    for key in ("version", "secrets", "clients", "rules", "skills", "hooks", "mcp_servers", "policy"):
        if key not in m:
            errs.append(f"missing top-level key {key}")
    if errs:
        return errs

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for n, v in enumerate(node):
                walk(v, f"{path}[{n}]")
        elif isinstance(node, str) and SECRET_RE.search(node):
            errs.append(f"{path}: value looks like a credential (redacted)")

    walk(m, "$")
    for name in m["secrets"].get("names", []):
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", name):
            errs.append(f"secrets.names: {name!r} is not an env var NAME")
    names = set()
    for s in m["mcp_servers"]:
        n = s.get("name")
        if n in names:
            errs.append(f"mcp_servers: duplicate name {n}")
        names.add(n)
        if s.get("transport") in ("http", "sse"):
            url = s.get("url", "")
            if not url.startswith("https://") or "?" in url:
                errs.append(f"mcp_servers.{n}: url must be https and carry no query string")
        if s.get("transport") == "stdio" and s.get("managed", True) and not s.get("pin"):
            errs.append(f"mcp_servers.{n}: stdio server needs a pin")
        for e in s.get("env_names", []) or []:
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", e):
                errs.append(f"mcp_servers.{n}: env_names entry {e!r} is not a NAME")
        for a in s.get("args", []) or []:
            if isinstance(a, str) and len(a) > 40 and not a.startswith(("-", "/", "~", "http", "$", "@")):
                errs.append(f"mcp_servers.{n}: long opaque arg (redacted); use an env NAME")
    return errs


# ---------------------------------------------------------------- live projections (names only)
def _proj_entry(v: dict) -> dict:
    headers = v.get("headers") or v.get("http_headers") or {}
    transport = v.get("type") or ("http" if v.get("url") else "stdio")
    if transport == "streamable-http":
        transport = "http"
    args = []
    for a in v.get("args") or []:
        a = str(a)
        args.append(a if len(a) <= 40 or a.startswith(("-", "/", "~", "http", "$", "@")) else "<arg>")
    return {
        "transport": transport,
        "command": v.get("command"),
        "args": args,
        "url": (v.get("url") or "").split("?")[0],
        "env_names": sorted((v.get("env") or {}).keys()),
        "header_names": sorted(headers.keys()),
        "header_literal": sorted(k for k, val in headers.items() if not ENV_REF_RE.search(str(val))),
        "bearer_env": v.get("bearer_token_env_var"),
        "enabled": v.get("enabled", True),
        "enabled_tools": sorted(v.get("enabled_tools") or []),
        "disabled_tools": sorted(v.get("disabled_tools") or []),
    }


def _norm(x, home: Path):
    if isinstance(x, str):
        return x.replace(str(home), "~", 1) if x.startswith(str(home)) else x
    if isinstance(x, list):
        return [_norm(i, home) for i in x]
    return x


def project_live(client: str, home: Path) -> tuple[dict | None, str]:
    rel, key, kind = CLIENT_FILES[client]
    p = Path(os.path.expanduser(rel.replace("~", str(home), 1)))
    if not p.exists():
        return None, f"{client}: missing {rel}"
    try:
        data = tomllib.loads(p.read_text()) if kind == "toml" else json.loads(p.read_text())
    except Exception as e:  # never print file content
        return None, f"{client}: unreadable {rel} ({type(e).__name__})"
    servers = data.get(key) or {}
    out = {}
    for name, v in servers.items():
        if isinstance(v, dict):
            e = _proj_entry(v)
            e["command"], e["args"] = _norm(e["command"], home), _norm(e["args"], home)
            out[name] = e
    return out, ""


def sha_prefix(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else "-"


# ---------------------------------------------------------------- render (projection of what would be written)
def render_projection(m: dict, client: str) -> dict:
    out = {}
    for s in m["mcp_servers"]:
        if not s.get("managed", True):
            continue
        flag = (s.get("clients") or {}).get(client, False)
        if flag in (False, "via_cursor", None):
            continue
        e = {"transport": s["transport"], "command": None, "args": [], "url": "", "env_names": [], "header_names": [],
             "header_literal": [], "bearer_env": None, "enabled": True, "enabled_tools": [], "disabled_tools": []}
        auth = s.get("auth") or {}
        if client == "claude_desktop" and s["transport"] == "http":
            e.update(transport="stdio", command="~/.claude/bin/mcp-remote-bearer", args=[auth.get("env", ""), s["url"]])
        elif s["transport"] == "stdio":
            e.update(command=s.get("command"), args=list(s.get("args") or []), env_names=sorted(s.get("env_names") or []))
        else:
            e["url"] = s["url"]
            kind = auth.get("claude_cli") if client == "claude_cli" and auth.get("claude_cli") else auth.get("kind")
            if kind in ("bearer_env", "header_env"):
                if client == "codex":
                    e["bearer_env"] = auth.get("env")
                else:
                    e["header_names"] = [auth.get("header", "Authorization")]
        if client == "codex":
            e["disabled_tools"] = sorted(t.split("__", 2)[2] for t in m["policy"].get("deny_tools", []) if t.split("__")[1] == s["name"] and not t.endswith("*"))
        out[s["name"]] = e
    return out


# ---------------------------------------------------------------- check
def check(m: dict, home: Path, state_path: Path | None) -> list[str]:
    drifts: list[str] = []
    state = {}
    if state_path and state_path.exists():
        state = json.loads(state_path.read_text())
    deny_caps = set(m["policy"].get("deny_capabilities", []))
    for s in m["mcp_servers"]:
        if deny_caps & set(s.get("capabilities", [])):
            for c, f in (s.get("clients") or {}).items():
                if f not in (False, None):
                    drifts.append(f"D-POLICY {s['name']}: capability {sorted(deny_caps & set(s['capabilities']))} enabled on {c}")
        pin = s.get("pin") or {}
        if pin.get("version") == "latest":
            drifts.append(f"D-PIN {s['name']}: version latest (manifest import); pin an exact version")
    for b in m.get("bridges", []):
        if b.get("pin") == "latest":
            drifts.append(f"D-PIN bridge {b['name']}: wraps {b['wraps']} unpinned")
        if b.get("sources_whole_env_file"):
            drifts.append(f"D-SECRET-SCOPE bridge {b['name']}: exports the whole env file to the child")
    for client in CLIENT_FILES:
        live, err = project_live(client, home)
        if live is None:
            drifts.append(f"D-FILE {err}")
            continue
        want = render_projection(m, client)
        for name, w in want.items():
            if name not in live:
                drifts.append(f"D-MISSING {client}: {name} not in live file")
                continue
            l = live[name]
            if l["transport"] != w["transport"]:
                drifts.append(f"D-TRANSPORT {client}: {name} live={l['transport']} want={w['transport']}")
            if w["transport"] == "stdio" and l["command"] != w["command"]:
                drifts.append(f"D-COMMAND {client}: {name}")
            if w["transport"] == "stdio" and l["args"] != w["args"]:
                drifts.append(f"D-ARGS {client}: {name}")
            if w["url"] and l["url"].rstrip("/") != w["url"].rstrip("/"):
                drifts.append(f"D-URL {client}: {name}")
            if l["env_names"] != w["env_names"]:
                drifts.append(f"D-ENV {client}: {name} live={l['env_names']} want={w['env_names']}")
            if l["header_literal"]:
                drifts.append(f"D-SECRET-INLINE {client}: {name} header(s) {l['header_literal']} hold a literal value, not an env reference")
            if client == "codex" and w["disabled_tools"] and l["disabled_tools"] != w["disabled_tools"]:
                drifts.append(f"D-TOOLGATE {client}: {name} disabled_tools live={l['disabled_tools']} want={w['disabled_tools']}")
            if not l["enabled"]:
                drifts.append(f"D-DISABLED {client}: {name} enabled=false in live file")
        for name, l in live.items():
            if name not in want:
                managed = next((s for s in m["mcp_servers"] if s["name"] == name), None)
                if managed and not managed.get("managed", True):
                    continue
                flag = (managed or {}).get("clients", {}).get(client) if managed else None
                if flag == "via_cursor":
                    continue
                drifts.append(f"D-UNMANAGED {client}: {name} present in live file but not enabled for {client} in manifest")
            if l["header_literal"] and name not in want:
                drifts.append(f"D-SECRET-INLINE {client}: {name} header(s) {l['header_literal']} hold a literal value")
        rel = CLIENT_FILES[client][0]
        p = Path(rel.replace("~", str(home), 1))
        if state.get(rel) and state[rel] != sha_prefix(p):
            drifts.append(f"D-OOB {client}: {rel} changed since stackctl last wrote it (hash mismatch)")
    # hooks
    hooks_files = {"codex": home / ".codex/hooks.json", "cursor": home / ".cursor/hooks.json", "claude_cli": home / ".claude/settings.json"}
    for h in m.get("hooks", []):
        if not h.get("managed", True):
            continue
        base = os.path.basename(re.sub(r"\s+-{1,2}\S.*$", "", str(h["source"])))
        for client, enabled in (h.get("clients") or {}).items():
            f = hooks_files.get(client)
            if not f or not f.exists():
                continue
            present = base in f.read_text()
            if enabled is True and not present:
                drifts.append(f"D-HOOK {client}: {h['name']} expected but not referenced in {f.name}")
            if enabled is False and present:
                drifts.append(f"D-HOOK {client}: {h['name']} referenced in {f.name} but disabled in manifest")
    # skills views
    canon = Path(str(m["skills"]["canonical"]).replace("~", str(home), 1))
    if canon.is_dir():
        for client, view in (m["skills"].get("views") or {}).items():
            vdir = Path(str(view["dir"]).replace("~", str(home), 1))
            if not vdir.is_dir():
                continue
            skip, prefixes = set(view.get("skip") or []), tuple(view.get("skip_prefixes") or [])
            want_names = {p.name for p in canon.iterdir() if (p / "SKILL.md").exists() and p.name not in skip and not p.name.startswith(prefixes)}
            have = {p.name for p in vdir.iterdir() if p.name != "README.md" and not p.name.startswith(".")}
            want_names |= set(view.get("extra") or [])
            if client == "codex" and view.get("native_reads_canonical") == "unknown":
                continue
            for n in sorted(want_names - have)[:50]:
                drifts.append(f"D-SKILL {client}: {n} missing from view")
            for n in sorted(have - want_names)[:50]:
                drifts.append(f"D-SKILL {client}: {n} in view but not expected")
            for p in vdir.iterdir():
                if p.is_dir() and not p.is_symlink() and not p.name.startswith(".") and p.name not in (view.get("extra") or []):
                    drifts.append(f"D-SKILL {client}: {p.name} is a real directory, not a link")
    # rules
    src = Path(str(m["rules"]["source"]).replace("~", str(home), 1))
    for client, t in (m["rules"].get("targets") or {}).items():
        f = Path(str(t["file"]).replace("~", str(home), 1))
        if not f.exists():
            drifts.append(f"D-RULES {client}: {t['file']} missing")
        elif t["mode"] == "symlink" and (not f.is_symlink() or f.resolve() != src.resolve()):
            drifts.append(f"D-RULES {client}: {t['file']} is not a symlink to the source")
        elif t["mode"] == "import" and str(m["rules"]["source"]).replace("~", str(home), 1) not in f.read_text() and "@" + str(m["rules"]["source"]) not in f.read_text():
            drifts.append(f"D-RULES {client}: {t['file']} does not import the source")
    return drifts


def cmd_render_dry(m: dict, home: Path) -> str:
    out = []
    for client in CLIENT_FILES:
        live, err = project_live(client, home)
        if live is None:
            out.append(f"## {client}: {err}")
            continue
        want = render_projection(m, client)
        a = json.dumps({k: live[k] for k in sorted(live)}, indent=1).splitlines()
        b = json.dumps({k: want[k] for k in sorted(want)}, indent=1).splitlines()
        rel = CLIENT_FILES[client][0]
        diff = list(difflib.unified_diff(a, b, f"live:{rel} (projection)", f"render:{rel} (projection)", lineterm=""))
        out.append(f"## {client}: would back up to {rel}.bak-stackctl-<date>; merge managed keys only; {len(diff)} diff lines")
        out.extend(diff[:200])
    out.append("## nothing written (dry-run)")
    return "\n".join(out)


# ---------------------------------------------------------------- selftest
FIXTURE_MANIFEST = """
version: 1
secrets:
  env_file: ~/.agents/mcp.env
  env_file_mode: "600"
  names: [FOO_TOKEN]
clients:
  claude_cli: {renderable: true}
rules:
  source: ~/.agents/AGENTS.md
  targets:
    codex: {mode: symlink, file: ~/.codex/AGENTS.md}
skills:
  canonical: ~/.agents/skills
  views:
    claude_cli: {dir: ~/.claude/skills, skip: [hidden]}
hooks:
  - name: guard-shell
    source: ~/.cursor/hooks/guard-shell.py
    event: shell_pre
    clients: {codex: true, cursor: false}
mcp_servers:
  - name: alpha
    transport: stdio
    command: ~/bin/alpha
    args: [mcp]
    pin: {kind: local-binary, path: ~/bin/alpha}
    env_names: [ALPHA_HOME]
    capabilities: [read]
    clients: {claude_cli: true, codex: true, cursor: true, claude_desktop: false, grok: false}
  - name: beta
    transport: http
    url: https://beta.example/mcp
    auth: {kind: bearer_env, env: FOO_TOKEN}
    capabilities: [read]
    clients: {claude_cli: true, codex: true, cursor: true, claude_desktop: false, grok: false}
  - name: trader
    transport: http
    url: https://trader.example/mcp
    auth: {kind: oauth}
    capabilities: [trade]
    clients: {claude_cli: false, codex: true, cursor: false, claude_desktop: false, grok: false}
  - name: unpinned
    transport: stdio
    command: npx
    args: [-y, thing@latest]
    pin: {kind: npx, package: thing, version: latest}
    capabilities: [read]
    clients: {claude_cli: true, codex: false, cursor: false, claude_desktop: false, grok: false}
policy:
  deny_capabilities: [trade]
  ask_capabilities: [send]
  deny_tools: [mcp__trader__place_order]
"""
FAKE = "Bearer FAKEFAKEFAKEFAKEFAKEFAKE0000000000"


def selftest() -> int:
    m = load_yaml(FIXTURE_MANIFEST)
    assert m["mcp_servers"][1]["auth"] == {"kind": "bearer_env", "env": "FOO_TOKEN"}, m["mcp_servers"][1]
    assert m["mcp_servers"][0]["clients"]["claude_cli"] is True
    assert m["hooks"][0]["clients"] == {"codex": True, "cursor": False}
    assert validate(m) == [], validate(m)
    bad = load_yaml(FIXTURE_MANIFEST.replace("env: FOO_TOKEN", f'env: "{FAKE}"'))
    assert any("credential" in e for e in validate(bad))
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / ".claude").mkdir()
        (home / ".cursor/hooks").mkdir(parents=True)
        (home / ".codex").mkdir()
        (home / ".agents/skills/visible").mkdir(parents=True)
        (home / ".agents/skills/visible/SKILL.md").write_text("x")
        (home / ".agents/skills/hidden").mkdir()
        (home / ".agents/skills/hidden/SKILL.md").write_text("x")
        (home / ".agents/AGENTS.md").write_text("rules")
        (home / ".claude/skills").mkdir()
        (home / ".claude/skills/stray").mkdir()
        (home / ".codex/AGENTS.md").write_text("not a link")
        (home / ".claude.json").write_text(json.dumps({"mcpServers": {
            "alpha": {"type": "stdio", "command": "~/bin/alpha", "args": ["mcp"], "env": {"ALPHA_HOME": "x", "EXTRA": "y"}},
            "beta": {"type": "http", "url": "https://beta.example/mcp?sig=abc", "headers": {"Authorization": FAKE}},
            "unpinned": {"type": "stdio", "command": "npx", "args": ["-y", "thing@latest"]},
            "ghost": {"type": "http", "url": "https://ghost.example/mcp"}}}))
        (home / ".cursor/mcp.json").write_text(json.dumps({"mcpServers": {
            "alpha": {"type": "stdio", "command": "~/bin/alpha", "args": ["mcp"], "env": {"ALPHA_HOME": "x"}},
            "beta": {"url": "https://beta.example/mcp", "headers": {"Authorization": "Bearer ${env:FOO_TOKEN}"}}}}))
        (home / ".codex/config.toml").write_text(
            '[mcp_servers.alpha]\ncommand = "~/bin/alpha"\nargs = ["mcp"]\n[mcp_servers.alpha.env]\nALPHA_HOME = "x"\n'
            '[mcp_servers.beta]\nurl = "https://beta.example/mcp"\nbearer_token_env_var = "FOO_TOKEN"\n'
            '[mcp_servers.trader]\nurl = "https://trader.example/mcp"\n')
        (home / ".codex/hooks.json").write_text(json.dumps({"hooks": {}}))
        (home / ".cursor/hooks.json").write_text(json.dumps({"hooks": {"beforeShellExecution": [{"command": "./hooks/guard-shell.py"}]}}))
        drifts = check(m, home, None)
        text = "\n".join(drifts)
        assert FAKE not in text and "FAKEFAKE" not in text, "secret leaked into report"
        for code in ("D-POLICY trader", "D-PIN unpinned", "D-ENV claude_cli: alpha", "D-SECRET-INLINE claude_cli: beta",
                     "D-UNMANAGED claude_cli: ghost", "D-TOOLGATE codex: trader", "D-HOOK codex: guard-shell",
                     "D-HOOK cursor: guard-shell", "D-SKILL claude_cli: visible missing", "D-SKILL claude_cli: stray",
                     "D-RULES codex", "D-FILE grok", "D-FILE claude_desktop"):
            assert any(code in d for d in drifts), f"expected {code}; got:\n{text}"
        assert not any("D-ENV cursor: alpha" in d for d in drifts)
        assert not any("D-SECRET-INLINE cursor" in d for d in drifts)
        rendered = cmd_render_dry(m, home)
        assert FAKE not in rendered and "nothing written" in rendered
        assert not (home / ".claude.json.bak-stackctl").exists()
    print(f"selftest ok: {len(drifts)} fixture drifts detected, no secret text in output")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", choices=["check", "render"])
    ap.add_argument("--manifest", default=str(Path(__file__).with_name("stack.yaml")))
    ap.add_argument("--home", default=str(Path.home()))
    ap.add_argument("--state", default=None, help="state file with hashes of files stackctl last wrote (default: none)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.command:
        ap.print_help()
        return 2
    m = load_yaml(Path(a.manifest).read_text())
    errs = validate(m)
    if errs:
        print("manifest invalid:\n  " + "\n  ".join(errs))
        return 2
    if a.command == "check":
        drifts = check(m, Path(a.home), Path(a.state) if a.state else None)
        if a.quiet:
            print(f"stackctl: {len(drifts)} drift(s)" if drifts else "stackctl: in sync")
        else:
            print("\n".join(drifts) if drifts else "in sync")
        return 1 if drifts else 0
    if not a.dry_run:
        print("render without --dry-run is not implemented in the prototype (writes nothing)")
        return 2
    print(cmd_render_dry(m, Path(a.home)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
