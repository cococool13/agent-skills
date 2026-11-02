#!/usr/bin/env python3
"""deps.py - read-only dependency inventory + OSV vulnerability lookup (stdlib only).

Parses package-lock.json (v1/v2/v3), bun.lock (text), pnpm-lock.yaml (v5-v9, minimal),
Package.resolved (v1/v2/v3) and emits:
  sbom-lite.csv            project,ecosystem,package,version,direct,vuln_count,max_severity,fix_version,scope,lockfile
  K.lockfiles.csv          one row per JS component dir (lockfiles, pm, CI install, node_modules)
  K.vulns.csv              one row per (vuln id, package@version, project)
  K.freshness.csv          direct npm deps: installed vs registry latest, major lag
  K.wrangler.csv           compatibility_date age + flags per wrangler config
  K.spm.csv                SwiftPM pin kinds (Package.swift, project.yml, Package.resolved)

Never installs, never writes inside the scanned tree. Network: api.osv.dev (POST querybatch,
GET vulns/<id>) and registry.npmjs.org (GET) only. Use --no-network to skip both.

Usage:
  deps.py scan  [--root ~/Projects] [--out DIR] [--today 2026-10-19] [--no-network] [--registry] [--spm-latest]
  deps.py --selftest
"""
import argparse, csv, datetime as dt, json, math, os, re, subprocess, sys, tempfile, time
import urllib.request, urllib.error, urllib.parse

PRUNE = {"node_modules", ".git", "dist", ".next", ".build", "SourcePackages", "_review",
         ".wrangler", "DerivedData", "build", ".astro", "Pods", ".turbo", ".svelte-kit",
         ".venv", "venv", "__pycache__", ".cache", ".output"}
LOCKS = {"package-lock.json": "npm", "bun.lock": "bun", "bun.lockb": "bun", "pnpm-lock.yaml": "pnpm",
         "yarn.lock": "yarn", "npm-shrinkwrap.json": "npm"}
MAX_DEPTH = 6
UA = "ai-stack-audit-deps/1.0 (read-only; cococool13)"

# ---------------------------------------------------------------- helpers
def jsonc_loads(text):
    # strip // and /* */ comments outside strings, trailing commas
    out, i, n, in_s = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_s:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"': in_s = False
            i += 1; continue
        if c == '"': in_s = True; out.append(c); i += 1; continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n": i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2); i = n if j < 0 else j + 2; continue
        out.append(c); i += 1
    s = "".join(out)
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    return json.loads(s)

def semver_key(v):
    v = v.lstrip("v=^~ ")
    core, _, pre = v.partition("-")
    core = core.split("+")[0]
    nums = []
    for p in core.split("."):
        m = re.match(r"\d+", p)
        nums.append(int(m.group()) if m else 0)
    while len(nums) < 3: nums.append(0)
    # release > prerelease
    pk = (1, ()) if not pre else (0, tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.split(r"[.-]", pre)))
    return (tuple(nums), pk)

def major(v):
    m = re.match(r"[v^~=\s]*(\d+)", v or "")
    return int(m.group(1)) if m else None

def roundup(x):
    i = int(round(x * 100000))
    return i / 100000.0 if i % 10000 == 0 else (math.floor(i / 10000) + 1) / 10.0

def cvss3_score(vec):
    try:
        m = dict(p.split(":") for p in vec.split("/")[1:])
        sc = m["S"] == "C"
        av = {"N": .85, "A": .62, "L": .55, "P": .2}[m["AV"]]
        ac = {"L": .77, "H": .44}[m["AC"]]
        pr = {"N": .85, "L": .68 if sc else .62, "H": .5 if sc else .27}[m["PR"]]
        ui = {"N": .85, "R": .62}[m["UI"]]
        cia = {"H": .56, "L": .22, "N": 0}
        iss = 1 - (1 - cia[m["C"]]) * (1 - cia[m["I"]]) * (1 - cia[m["A"]])
        imp = 7.52 * (iss - .029) - 3.25 * (iss - .02) ** 15 if sc else 6.42 * iss
        if imp <= 0: return 0.0
        ex = 8.22 * av * ac * pr * ui
        return roundup(min(1.08 * (imp + ex), 10)) if sc else roundup(min(imp + ex, 10))
    except Exception:
        return None

SEV_ORDER = {"UNKNOWN": 0, "LOW": 1, "MODERATE": 2, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
def band(score):
    return "CRITICAL" if score >= 9 else "HIGH" if score >= 7 else "MODERATE" if score >= 4 else "LOW"

def vuln_severity(v):
    s = (v.get("database_specific") or {}).get("severity")
    if s: return s.upper().replace("MEDIUM", "MODERATE")
    for e in v.get("affected", []):
        s = (e.get("database_specific") or {}).get("severity")
        if s: return s.upper().replace("MEDIUM", "MODERATE")
    for sv in v.get("severity", []) or []:
        sc = sv.get("score", "")
        if sc.startswith("CVSS:3"):
            x = cvss3_score(sc)
            if x is not None: return band(x)
    return "UNKNOWN"

def fixed_for(v, eco, name, ver):
    """smallest 'fixed' event greater than ver for the matching affected entry."""
    best = None
    for e in v.get("affected", []):
        p = e.get("package") or {}
        if p.get("ecosystem") != eco or (p.get("name") or "").lower() != name.lower(): continue
        for r in e.get("ranges", []):
            if r.get("type") not in ("SEMVER", "ECOSYSTEM"): continue
            for ev in r.get("events", []):
                f = ev.get("fixed")
                if f and semver_key(f) > semver_key(ver):
                    if best is None or semver_key(f) < semver_key(best): best = f
    return best

# ---------------------------------------------------------------- lockfile parsers -> [(name, version, direct_bool)]
def parse_package_lock(path, directs):
    d = json.load(open(path))
    rows = {}
    pk = d.get("packages")
    if pk:
        for k, v in pk.items():
            if not k or v.get("link"): continue
            name = k.rsplit("node_modules/", 1)[-1] if "node_modules/" in k else k
            ver = v.get("version")
            if ver: rows[(name, ver)] = name in directs
    else:
        def walk(deps):
            for n, v in (deps or {}).items():
                if v.get("version"): rows[(n, v["version"])] = n in directs
                walk(v.get("dependencies"))
        walk(d.get("dependencies"))
    return [(n, v, di) for (n, v), di in rows.items()]

def parse_bun_lock(path, directs):
    d = jsonc_loads(open(path).read())
    rows = {}
    for k, v in (d.get("packages") or {}).items():
        if not isinstance(v, list) or not v: continue
        spec = v[0]
        i = spec.rfind("@")
        if i <= 0: continue
        name, ver = spec[:i], spec[i + 1:]
        rows[(name, ver)] = name in directs
    return [(n, v, di) for (n, v), di in rows.items()]

def parse_pnpm_lock(path, directs):
    lines = open(path).read().splitlines()
    lv = 9.0
    for l in lines[:5]:
        m = re.match(r"lockfileVersion:\s*'?\"?([\d.]+)", l)
        if m: lv = float(m.group(1))
    rows, inpk = {}, False
    for l in lines:
        if re.match(r"^\S", l): inpk = l.startswith("packages:")
        if not inpk: continue
        m = re.match(r"^  ('?)([^\s'][^']*?)\1:\s*$", l)
        if not m: continue
        key = m.group(2).lstrip("/")
        key = key.split("(")[0]
        if lv < 6:  # /name/1.2.3_peer
            key = key.split("_")[0]
            name, _, ver = key.rpartition("/")
        else:
            i = key.rfind("@")
            if i <= 0: continue
            name, ver = key[:i], key[i + 1:]
        if name and ver and re.match(r"\d", ver): rows[(name, ver)] = name in directs
    return [(n, v, di) for (n, v), di in rows.items()]

def parse_package_resolved(path, directs_text=""):
    d = json.load(open(path))
    pins = d.get("pins") or (d.get("object") or {}).get("pins") or []
    out = []
    for p in pins:
        ident = p.get("identity") or (p.get("package") or "").lower()
        loc = p.get("location") or p.get("repositoryURL") or ""
        st = p.get("state") or {}
        kind = "version" if st.get("version") else ("branch" if st.get("branch") else "revision")
        slug = re.sub(r"\.git$", "", loc.rstrip("/")).split("/")[-1].lower()
        out.append({"identity": ident, "location": loc, "version": st.get("version"), "branch": st.get("branch"),
                    "revision": st.get("revision"), "kind": kind, "direct": slug in directs_text or ident in directs_text})
    return out

def swift_osv_name(loc):
    u = re.sub(r"^(https?://|git@|ssh://git@)", "", loc)
    u = u.replace(":", "/", 1) if "://" not in loc and "@" in loc else u
    return re.sub(r"\.git$", "", u.rstrip("/"))

# ---------------------------------------------------------------- OSV
class Osv:
    def __init__(self, cache_path, offline=False):
        self.cache_path, self.offline = cache_path, offline
        self.cache = {"q": {}, "v": {}}
        if cache_path and os.path.exists(cache_path):
            try: self.cache = json.load(open(cache_path))
            except Exception: pass

    def save(self):
        if self.cache_path:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            json.dump(self.cache, open(self.cache_path, "w"))

    def _req(self, url, body=None):
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"User-Agent": UA, "Content-Type": "application/json"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503): time.sleep(2 * (attempt + 1)); continue
                raise
            except Exception:
                time.sleep(2 * (attempt + 1))
        return None

    def query(self, items):
        """items: list of (kind, a, b, c): ('pkg', eco, name, ver) or ('commit', rev). returns {key: [vuln ids]}"""
        keys = [json.dumps(i) for i in items]
        todo = [(k, i) for k, i in zip(keys, items) if k not in self.cache["q"]]
        if todo and not self.offline:
            for s in range(0, len(todo), 1000):
                chunk = todo[s:s + 1000]
                qs = [{"package": {"name": i[2], "ecosystem": i[1]}, "version": i[3]} if i[0] == "pkg"
                      else {"commit": i[1]} for _, i in chunk]
                res = self._req("https://api.osv.dev/v1/querybatch", {"queries": qs})
                if not res: continue
                for (k, _), r in zip(chunk, res.get("results", [])):
                    self.cache["q"][k] = [v["id"] for v in r.get("vulns", [])]
                time.sleep(0.5)
            self.save()
        return {k: self.cache["q"].get(k) for k in keys}

    def vuln(self, vid):
        if vid in self.cache["v"]: return self.cache["v"][vid]
        if self.offline: return None
        v = self._req("https://api.osv.dev/v1/vulns/" + urllib.parse.quote(vid))
        time.sleep(0.2)
        if v is not None: self.cache["v"][vid] = v
        return v

# ---------------------------------------------------------------- discovery
def walk_projects(root):
    """yield (project, rel_dir, abs_dir, files, dirs) with pruning; project = top-level (or archive/X)."""
    root = os.path.abspath(root)
    for top in sorted(os.listdir(root)):
        tp = os.path.join(root, top)
        if top in PRUNE or not os.path.isdir(tp) or os.path.islink(tp): continue
        subs = [(top, tp)]
        if top == "archive":
            subs = [("archive/" + s, os.path.join(tp, s)) for s in sorted(os.listdir(tp)) if os.path.isdir(os.path.join(tp, s))]
        for proj, base in subs:
            for dp, dns, fns in os.walk(base):
                dns[:] = [d for d in dns if d not in PRUNE and not os.path.islink(os.path.join(dp, d))]
                rel = os.path.relpath(dp, base)
                if rel != "." and rel.count(os.sep) + 1 > MAX_DEPTH: dns[:] = []; continue
                yield proj, ("" if rel == "." else rel), dp, fns, dns

def scope_of(rel, proj=""):
    if proj.startswith("archive/"): return "archive"
    parts = rel.split(os.sep)
    if any(p in ("_archive", "archive") for p in parts): return "archive"
    if any(p in ("scratch", "_scratch", "pkg-wt") for p in parts): return "scratch"
    return "active"

def read_json(p):
    try: return json.load(open(p))
    except Exception: return {}

CI_PAT = [("npm ci", r"\bnpm ci\b"), ("npm install", r"\bnpm (install|i)\b(?! -g)(?![^\n]*--(frozen|package-lock-only))"),
          ("bun --frozen", r"bun install[^\n]*--frozen-lockfile|bun ci\b"), ("bun install", r"\bbun install\b(?![^\n]*--frozen-lockfile)"),
          ("pnpm --frozen", r"pnpm (i|install)[^\n]*--frozen-lockfile"), ("pnpm install", r"\bpnpm (i|install)\b(?![^\n]*--frozen-lockfile)"),
          ("yarn --frozen", r"yarn install[^\n]*--(frozen-lockfile|immutable)"), ("yarn install", r"\byarn( install)?\s*$")]
def ci_info(proj_dir):
    wfs = []
    for dp, dns, fns in os.walk(proj_dir):
        dns[:] = [d for d in dns if d not in PRUNE]
        if dp.endswith(os.path.join(".github", "workflows")):
            wfs += [os.path.join(dp, f) for f in fns if f.endswith((".yml", ".yaml"))]
            dns[:] = []
    cmds = set()
    for w in wfs:
        txt = open(w, errors="ignore").read()
        for name, pat in CI_PAT:
            if re.search(pat, txt, re.M): cmds.add(name)
    return wfs, sorted(cmds)

def js_components(root):
    comps = []
    for proj, rel, dp, fns, dns in walk_projects(root):
        locks = [f for f in fns if f in LOCKS]
        if "package.json" in fns or locks:
            comps.append((proj, rel, dp, fns, locks))
    return comps

# ---------------------------------------------------------------- wrangler
def parse_wrangler(path, today):
    txt = open(path, errors="ignore").read()
    if path.endswith(".toml"):
        cd = re.search(r'^\s*compatibility_date\s*=\s*"([\d-]+)"', txt, re.M)
        fl = re.search(r'^\s*compatibility_flags\s*=\s*\[([^\]]*)\]', txt, re.M)
        nm = re.search(r'^\s*name\s*=\s*"([^"]+)"', txt, re.M)
        flags = re.findall(r'"([^"]+)"', fl.group(1)) if fl else []
        name = nm.group(1) if nm else ""; cdv = cd.group(1) if cd else ""
    else:
        try: d = jsonc_loads(txt)
        except Exception: return None
        cdv, flags, name = d.get("compatibility_date", ""), d.get("compatibility_flags", []), d.get("name", "")
    age = (today - dt.date.fromisoformat(cdv)).days if re.match(r"\d{4}-\d\d-\d\d$", cdv or "") else ""
    return name, cdv, age, ";".join(flags)

# ---------------------------------------------------------------- SwiftPM static scan
def scan_swift(dp, fns):
    rows = []
    if "Package.swift" in fns:
        txt = open(os.path.join(dp, "Package.swift"), errors="ignore").read()
        for m in re.finditer(r"\.package\(\s*(?:name:\s*\"[^\"]*\",\s*)?url:\s*\"([^\"]+)\"\s*,\s*([^)]*?)\)", txt, re.S):
            spec = " ".join(m.group(2).split())
            kind = "branch" if "branch:" in spec else "revision" if "revision:" in spec else \
                   "exact" if "exact:" in spec or "exactVersion" in spec else "range"
            rows.append(("Package.swift", m.group(1), spec[:80], kind))
        for m in re.finditer(r"\.package\(\s*path:\s*\"([^\"]+)\"", txt):
            rows.append(("Package.swift", "path:" + m.group(1), "local", "local"))
    if "project.yml" in fns:
        txt = open(os.path.join(dp, "project.yml"), errors="ignore").read().splitlines()
        inp, cur = False, None
        for l in txt:
            if re.match(r"^\S", l): inp = l.startswith("packages:")
            if not inp: continue
            m = re.match(r"^  ([\w.-]+):\s*$", l)
            if m: cur = {"name": m.group(1)}; rows.append(("project.yml", cur, "", "")); continue
            m = re.match(r"^    (url|path|from|exactVersion|exact|branch|revision|minVersion|majorVersion|minorVersion|version):\s*(.+)$", l)
            if m and cur is not None: cur[m.group(1)] = m.group(2).strip().strip("\"'")
        fixed = []
        for r in rows:
            if r[0] == "project.yml" and isinstance(r[1], dict):
                c = r[1]
                loc = c.get("url") or ("path:" + c["path"] if "path" in c else c["name"])
                kind = "local" if "path" in c else "branch" if "branch" in c else "revision" if "revision" in c else \
                       "exact" if ("exactVersion" in c or "exact" in c) else "range"
                spec = ",".join(f"{k}={v}" for k, v in c.items() if k not in ("name", "url", "path"))
                fixed.append(("project.yml", loc, spec, kind))
            else: fixed.append(r)
        rows = fixed
    return rows

# ---------------------------------------------------------------- scan
def scan(a):
    root = os.path.expanduser(a.root); out = os.path.expanduser(a.out); today = dt.date.fromisoformat(a.today)
    os.makedirs(os.path.join(out, "workstreams"), exist_ok=True)
    cache = os.path.join(out, "scratch", "K-osv-cache.json")
    osv = Osv(cache, offline=a.no_network)
    comps = js_components(root)
    sbom, lockrows = [], []
    proj_cache_ci = {}
    swift_pins = []   # dict rows
    swift_static = []
    wr = []
    for proj, rel, dp, fns, dns in walk_projects(root):
        loc = proj + ("/" + rel if rel else "")
        sc = scope_of(rel, proj)
        if "Package.resolved" in fns or "Package.swift" in fns or "project.yml" in fns:
            for k, u, spec, kind in scan_swift(dp, fns):
                swift_static.append((proj, rel, sc, k, u, spec, kind))
        for f in fns:
            if f.startswith("wrangler.") and f.endswith((".toml", ".json", ".jsonc")):
                r = parse_wrangler(os.path.join(dp, f), today)
                if r: wr.append((proj, os.path.join(rel, f), sc) + r)
        if "Package.resolved" in fns:
            # direct-ness: look for slug in any project.yml / Package.swift of the project tree
            txts = ""
            for dp2, d2, f2 in os.walk(os.path.join(root, proj.split("/")[0], *proj.split("/")[1:])):
                d2[:] = [d for d in d2 if d not in PRUNE]
                for ff in f2:
                    if ff in ("Package.swift", "project.yml"): txts += open(os.path.join(dp2, ff), errors="ignore").read().lower()
            for p in parse_package_resolved(os.path.join(dp, "Package.resolved"), txts):
                swift_pins.append((proj, rel, sc, p))
    # npm-style
    for proj, rel, dp, fns, locks in comps:
        pj = read_json(os.path.join(dp, "package.json")) if "package.json" in fns else {}
        directs = set()
        for k in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
            directs |= set((pj.get(k) or {}).keys())
        mgrs = sorted({LOCKS[l] for l in locks})
        top = proj
        if top not in proj_cache_ci:
            proj_cache_ci[top] = ci_info(os.path.join(root, *top.split("/")))
        wfs, cmds = proj_cache_ci[top]
        frozen = "n/a (no CI)" if not wfs else ("yes" if any(c.endswith("frozen") or c == "npm ci" for c in cmds) and
                 not any(c in ("npm install", "bun install", "pnpm install", "yarn install") for c in cmds) else
                 ("partial" if any(c.endswith("frozen") or c == "npm ci" for c in cmds) else ("no" if cmds else "no install step")))
        lockrows.append({
            "project": proj, "component": rel or ".", "scope": scope_of(rel, proj), "package_json": "package.json" in fns,
            "lockfiles": ";".join(locks), "pm_count": len(mgrs), "package_manager_field": pj.get("packageManager", ""),
            "engines": json.dumps(pj.get("engines", {}), separators=(",", ":")) if pj.get("engines") else "",
            "workspaces": "yes" if pj.get("workspaces") else "", "ci_workflows": len(wfs), "ci_install_cmds": ";".join(cmds),
            "ci_frozen": frozen, "node_modules": os.path.isdir(os.path.join(dp, "node_modules")),
            "issue": ("no-lockfile" if "package.json" in fns and not locks else
                      "multiple-lockfiles" if len(locks) > 1 else "lock-without-package.json" if locks and "package.json" not in fns else
                      "binary-bun.lockb-unparsed" if "bun.lockb" in locks else ""),
            "deps": len(pj.get("dependencies") or {}), "devDeps": len(pj.get("devDependencies") or {}),
            "scripts_install_hooks": ";".join(k for k in (pj.get("scripts") or {}) if k in ("preinstall", "install", "postinstall", "prepare")),
        })
        for lf in locks:
            lp = os.path.join(dp, lf); rows = []
            try:
                if lf in ("package-lock.json", "npm-shrinkwrap.json"): rows = parse_package_lock(lp, directs)
                elif lf == "bun.lock": rows = parse_bun_lock(lp, directs)
                elif lf == "pnpm-lock.yaml": rows = parse_pnpm_lock(lp, directs)
            except Exception as e:
                print(f"WARN parse {lp}: {e}", file=sys.stderr)
            for n, v, di in rows:
                sbom.append({"project": proj + ("/" + rel if rel else ""), "ecosystem": "npm", "package": n, "version": v,
                             "direct": "direct" if di else "transitive", "scope": scope_of(rel, proj), "lockfile": lf})
    for proj, rel, sc, p in swift_pins:
        sbom.append({"project": proj + ("/" + rel if rel else ""), "ecosystem": "SwiftURL", "package": p["identity"],
                     "version": p["version"] or (("branch:" + p["branch"]) if p["branch"] else "rev:" + (p["revision"] or "")[:10]),
                     "direct": "direct" if p["direct"] else "transitive", "scope": sc, "lockfile": "Package.resolved",
                     "_loc": p["location"], "_rev": p["revision"], "_kind": p["kind"]})
    # ---- OSV
    qitems, qkey = [], {}
    for r in sbom:
        if r["ecosystem"] == "npm":
            if re.match(r"\d+\.\d+\.\d+", r["version"]): qitems.append(("pkg", "npm", r["package"], r["version"]))
        else:
            if r["_kind"] == "version":
                qitems.append(("pkg", "SwiftURL", swift_osv_name(r["_loc"]), r["version"]))
            if r["_rev"]: qitems.append(("commit", r["_rev"]))
    qitems = [list(x) for x in {tuple(x) for x in qitems}]
    qres = osv.query(qitems) if qitems else {}
    vulns_seen = {}
    for r in sbom:
        ids = set()
        if r["ecosystem"] == "npm":
            ids |= set(qres.get(json.dumps(["pkg", "npm", r["package"], r["version"]])) or [])
            eco, nm = "npm", r["package"]
        else:
            if r["_kind"] == "version":
                ids |= set(qres.get(json.dumps(["pkg", "SwiftURL", swift_osv_name(r["_loc"]), r["version"]])) or [])
            if r["_rev"]: ids |= set(qres.get(json.dumps(["commit", r["_rev"]])) or [])
            eco, nm = "SwiftURL", swift_osv_name(r["_loc"])
        best, fixes, det = "", set(), []
        for vid in sorted(ids):
            v = osv.vuln(vid)
            if not v: continue
            sev = vuln_severity(v); fx = fixed_for(v, eco, nm, r["version"]) if eco == "npm" else None
            if best == "" or SEV_ORDER.get(sev, 0) > SEV_ORDER.get(best, 0): best = sev
            if fx: fixes.add(fx)
            det.append((vid, sev, fx or "", (v.get("summary") or "")[:110]))
        r["vuln_count"] = len(det); r["max_severity"] = best
        r["fix_version"] = max(fixes, key=semver_key) if fixes else ""
        r["_det"] = det
    osv.save()
    # ---- write sbom
    sbom.sort(key=lambda r: (r["project"], r["ecosystem"], r["package"], r["version"]))
    with open(os.path.join(out, "sbom-lite.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["project", "ecosystem", "package", "version", "direct/transitive", "vuln_count", "max_severity", "fix_version", "scope", "lockfile"])
        for r in sbom:
            w.writerow([r["project"], r["ecosystem"], r["package"], r["version"], r["direct"], r["vuln_count"], r["max_severity"], r["fix_version"], r["scope"], r["lockfile"]])
    with open(os.path.join(out, "workstreams", "K.vulns.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["project", "scope", "ecosystem", "package", "version", "direct", "vuln_id", "severity", "fix_version", "summary"])
        for r in sbom:
            for vid, sev, fx, sm in r["_det"]:
                w.writerow([r["project"], r["scope"], r["ecosystem"], r["package"], r["version"], r["direct"], vid, sev, fx, sm])
    lockrows.sort(key=lambda r: (r["project"], r["component"]))
    with open(os.path.join(out, "workstreams", "K.lockfiles.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(lockrows[0].keys())); w.writeheader(); w.writerows(lockrows)
    with open(os.path.join(out, "workstreams", "K.wrangler.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["project", "file", "scope", "name", "compatibility_date", "age_days", "compatibility_flags"])
        for r in sorted(wr): w.writerow(r)
    # ---- spm table
    pins_by = {}
    for proj, rel, sc, p in swift_pins: pins_by.setdefault((proj, rel), []).append(p)
    with open(os.path.join(out, "workstreams", "K.spm.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["project", "dir", "scope", "source", "dependency", "spec", "kind", "resolved_version", "latest_release"])
        latest_cache = {}
        def latest(url):
            if not a.spm_latest or "github.com" not in url: return ""
            m = re.search(r"github.com[/:]([^/]+)/([^/.]+)", url)
            if not m: return ""
            k = m.group(1) + "/" + m.group(2)
            if k not in latest_cache:
                try:
                    o = subprocess.run(["gh", "api", f"repos/{k}/releases/latest", "--jq", ".tag_name"], capture_output=True, text=True, timeout=30)
                    latest_cache[k] = o.stdout.strip() if o.returncode == 0 else "n/a"
                except Exception: latest_cache[k] = "n/a"
                time.sleep(0.5)
            return latest_cache[k]
        for proj, rel, sc, k, u, spec, kind in swift_static:
            res = ""
            for p in pins_by.get((proj, rel), []):
                if isinstance(u, str) and p["identity"] in u.lower(): res = p["version"] or p["branch"] or (p["revision"] or "")[:10]
            w.writerow([proj, rel, sc, k, u, spec, kind, res, latest(u) if isinstance(u, str) else ""])
        for proj, rel, sc, p in swift_pins:
            w.writerow([proj, rel, sc, "Package.resolved", p["location"], "", p["kind"], p["version"] or p["branch"] or (p["revision"] or "")[:10], latest(p["location"])])
    # ---- freshness
    if a.registry and not a.no_network:
        want = {}
        for r in sbom:
            if r["ecosystem"] == "npm" and r["direct"] == "direct" and r["scope"] == "active": want.setdefault(r["package"], None)
        reg_cache_p = os.path.join(out, "scratch", "K-npm-latest.json")
        rc = json.load(open(reg_cache_p)) if os.path.exists(reg_cache_p) else {}
        for n in sorted(want):
            if n in rc: continue
            try:
                req = urllib.request.Request("https://registry.npmjs.org/" + urllib.parse.quote(n, safe="@") + "/latest", headers={"User-Agent": UA})
                rc[n] = json.load(urllib.request.urlopen(req, timeout=30)).get("version", "")
            except Exception: rc[n] = ""
            time.sleep(0.5)
        json.dump(rc, open(reg_cache_p, "w"))
        with open(os.path.join(out, "workstreams", "K.freshness.csv"), "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["project", "package", "installed", "latest", "major_lag"])
            for r in sbom:
                if r["ecosystem"] == "npm" and r["direct"] == "direct" and r["scope"] == "active":
                    lt = rc.get(r["package"], ""); mi, ml = major(r["version"]), major(lt)
                    w.writerow([r["project"], r["package"], r["version"], lt, (ml - mi) if (mi is not None and ml is not None) else ""])
    print(f"sbom rows={len(sbom)} components={len(lockrows)} wrangler={len(wr)} swift_pins={len(swift_pins)} queries={len(qitems)}")

# ---------------------------------------------------------------- selftest
def selftest():
    assert semver_key("1.10.0") > semver_key("1.9.9") and semver_key("1.0.0") > semver_key("1.0.0-rc.1")
    assert major("^5.2.1") == 5 and major("v10.0.0") == 10
    s = cvss3_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"); assert s == 9.8, s
    assert vuln_severity({"database_specific": {"severity": "MEDIUM"}}) == "MODERATE"
    assert vuln_severity({"severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}]}) == "CRITICAL"
    v = {"affected": [{"package": {"ecosystem": "npm", "name": "x"}, "ranges": [{"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "1.2.3"}, {"introduced": "2.0.0"}, {"fixed": "2.1.0"}]}]}]}
    assert fixed_for(v, "npm", "x", "1.0.0") == "1.2.3" and fixed_for(v, "npm", "x", "2.0.5") == "2.1.0"
    assert swift_osv_name("https://github.com/apple/swift-nio.git") == "github.com/apple/swift-nio"
    with tempfile.TemporaryDirectory() as t:
        j = lambda n, o: json.dump(o, open(os.path.join(t, n), "w"))
        j("pl.json", {"lockfileVersion": 3, "packages": {"": {}, "node_modules/a": {"version": "1.0.0"}, "node_modules/a/node_modules/@s/b": {"version": "2.0.0"}, "node_modules/l": {"link": True}}})
        r = parse_package_lock(os.path.join(t, "pl.json"), {"a"}); assert sorted(r) == [("@s/b", "2.0.0", False), ("a", "1.0.0", True)], r
        open(os.path.join(t, "bun.lock"), "w").write('{\n // c\n "lockfileVersion": 1,\n "packages": {\n "foo": ["foo@3.1.4", "", {}, "sha"],\n "@x/y": ["@x/y@0.1.0", "", {},],\n },\n}\n')
        r = parse_bun_lock(os.path.join(t, "bun.lock"), {"foo"}); assert sorted(r) == [("@x/y", "0.1.0", False), ("foo", "3.1.4", True)], r
        open(os.path.join(t, "p9.yaml"), "w").write("lockfileVersion: '9.0'\n\nimporters:\n  .:\n    dependencies:\n      q:\n        specifier: ^1\n        version: 1.2.3\n\npackages:\n\n  '@scope/n@4.5.6':\n    resolution: {integrity: x}\n\n  q@1.2.3(react@18.0.0):\n    resolution: {integrity: y}\n\nsnapshots:\n  q@1.2.3: {}\n")
        r = parse_pnpm_lock(os.path.join(t, "p9.yaml"), {"q"}); assert sorted(r) == [("@scope/n", "4.5.6", False), ("q", "1.2.3", True)], r
        open(os.path.join(t, "p5.yaml"), "w").write("lockfileVersion: 5.4\npackages:\n  /@a/b/1.0.0_c@2:\n    x: 1\n  /d/2.0.0:\n    x: 1\n")
        r = parse_pnpm_lock(os.path.join(t, "p5.yaml"), set()); assert sorted(r) == [("@a/b", "1.0.0", False), ("d", "2.0.0", False)], r
        j("Package.resolved", {"version": 2, "pins": [{"identity": "sparkle", "location": "https://github.com/sparkle-project/Sparkle", "state": {"revision": "abc", "version": "2.6.0"}},
                                                      {"identity": "br", "location": "https://github.com/o/br.git", "state": {"branch": "main", "revision": "def"}}]})
        r = parse_package_resolved(os.path.join(t, "Package.resolved"), "sparkle-project/sparkle"); assert [p["kind"] for p in r] == ["version", "branch"] and r[0]["direct"], r
        j("w.jsonc", {})
        open(os.path.join(t, "wrangler.jsonc"), "w").write('{\n // c "x"\n "name": "u//rl", "compatibility_date": "2026-01-01", "compatibility_flags": ["nodejs_compat"],\n}\n')
        wv = parse_wrangler(os.path.join(t, "wrangler.jsonc"), dt.date(2026, 10, 19)); assert wv == ("u//rl", "2026-01-01", 291, "nodejs_compat"), wv
        open(os.path.join(t, "wrangler.toml"), "w").write('name = "w"\ncompatibility_date = "2025-10-19"\ncompatibility_flags = ["a", "b"]\n')
        wv = parse_wrangler(os.path.join(t, "wrangler.toml"), dt.date(2026, 10, 19)); assert wv == ("w", "2025-10-19", 365, "a;b"), wv
        # end-to-end offline scan on a synthetic tree
        root = os.path.join(t, "Projects", "Demo"); os.makedirs(os.path.join(root, "site")); os.makedirs(os.path.join(root, ".github", "workflows"))
        json.dump({"name": "d", "dependencies": {"a": "^1"}, "packageManager": "npm@10"}, open(os.path.join(root, "site", "package.json"), "w"))
        json.dump({"lockfileVersion": 3, "packages": {"node_modules/a": {"version": "1.0.0"}}}, open(os.path.join(root, "site", "package-lock.json"), "w"))
        open(os.path.join(root, ".github", "workflows", "ci.yml"), "w").write("steps:\n  - run: npm ci\n")
        ns = argparse.Namespace(root=os.path.join(t, "Projects"), out=os.path.join(t, "out"), today="2026-10-19", no_network=True, registry=False, spm_latest=False)
        scan(ns)
        rows = list(csv.DictReader(open(os.path.join(t, "out", "sbom-lite.csv")))); assert rows[0]["package"] == "a" and rows[0]["direct/transitive"] == "direct", rows
        lk = list(csv.DictReader(open(os.path.join(t, "out", "workstreams", "K.lockfiles.csv")))); assert lk[0]["ci_frozen"] == "yes" and lk[0]["pm_count"] == "1", lk
    print("selftest ok")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="scan")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", default="~/Projects")
    ap.add_argument("--out", default="~/Projects/_review/ai-stack-audit-2026-10-19")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--no-network", action="store_true")
    ap.add_argument("--registry", action="store_true")
    ap.add_argument("--spm-latest", action="store_true")
    a = ap.parse_args()
    if a.selftest: selftest()
    else: scan(a)
