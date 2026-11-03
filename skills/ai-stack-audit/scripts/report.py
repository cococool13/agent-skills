#!/usr/bin/env python3 -I
"""report.py - summarize one ai-stack-audit run dir, or diff it against a previous run.

Usage
  report.py RUN_DIR                          summary: findings by severity/area, top 10, metric count
  report.py RUN_DIR --diff PREV_RUN_DIR      new / resolved / regressed / improved / unchanged findings
                                             (by fingerprint), metric deltas, baseline count deltas,
                                             config hash changes, MCP tool-definition hash changes
  report.py RUN_DIR ... --json               machine-readable output
  report.py --fingerprint AREA PATH RULE     print the canonical fingerprint
  report.py --selftest                       uses fixtures/report/run-a and run-b

A run dir holds findings.jsonl (falls back to findings.all.jsonl), metrics.json, baseline.json and
baseline-mcp-tools.json; each one is optional. Read-only: reads those files, writes nothing.
Allowlisted: python stdlib, redact.sh, mcp-hashes.py (diff only). All stdout goes through redact.sh.
"""
import hashlib, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REDACT = os.path.join(HERE, "redact.sh")
MCPH = os.path.join(HERE, "mcp-hashes.py")
SEV = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
CONF = {"high": 1.0, "med": 0.6, "medium": 0.6, "low": 0.3}
EFF = {"S": 1, "M": 2, "L": 4}


def emit(text):
    r = subprocess.run([REDACT], input=text, capture_output=True, text=True, check=True)
    sys.stdout.write(r.stdout)


def norm_path(p):
    p = (p or "").strip()
    home = os.path.expanduser("~")
    if p.startswith(home):
        p = "~" + p[len(home):]
    p = re.sub(r":\d+(-\d+)?$", "", p)                 # drop :line or :a-b
    p = re.sub(r"\d{4}-\d{2}-\d{2}", "YYYY-MM-DD", p)   # run-dir dates
    p = re.sub(r"\.bak[\w.-]*$", ".bak*", p)            # backup suffixes
    return p.rstrip("/").lower()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def fingerprint(area, path, rule):
    return hashlib.sha256(f"{area.strip().lower()}|{norm_path(path)}|{slug(rule)}".encode()).hexdigest()[:16]


def load(run):
    d = {"dir": run, "findings": [], "metrics": {}, "baseline": {}, "mcp": None}
    for name in ("findings.jsonl", "findings.all.jsonl"):
        p = os.path.join(run, name)
        if os.path.exists(p):
            d["findings"] = [json.loads(l) for l in open(p) if l.strip()]
            d["findings_file"] = name
            break
    for key, name in (("metrics", "metrics.json"), ("baseline", "baseline.json")):
        p = os.path.join(run, name)
        if os.path.exists(p):
            d[key] = json.load(open(p))
    p = os.path.join(run, "baseline-mcp-tools.json")
    d["mcp"] = p if os.path.exists(p) else None
    return d


def fp_of(f):
    if f.get("fingerprint"):
        return f["fingerprint"]
    ev = (f.get("evidence") or [{}])[0]
    return fingerprint(f.get("area", ""), ev.get("path", ""), f.get("rule") or f.get("title", ""))


def score(f):
    return float(f.get("impact", 3)) * CONF.get(str(f.get("confidence", "med")).lower(), 0.6) / EFF.get(f.get("effort", "M"), 2)


def flatten(o, pre=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flatten(v, f"{pre}.{k}" if pre else str(k)))
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        out[pre] = o
    return out


def summary(run):
    fs = run["findings"]
    by_sev, by_area = {}, {}
    for f in fs:
        by_sev[f.get("severity")] = by_sev.get(f.get("severity"), 0) + 1
        by_area[f.get("area")] = by_area.get(f.get("area"), 0) + 1
    top = sorted(fs, key=lambda f: (-score(f), SEV.get(f.get("severity"), 9)))[:10]
    return {"run": run["dir"], "findings_file": run.get("findings_file"), "findings": len(fs),
            "by_severity": dict(sorted(by_sev.items(), key=lambda kv: str(kv[0]))),
            "by_area": dict(sorted(by_area.items(), key=lambda kv: -kv[1])),
            "top10": [{"id": f.get("id"), "severity": f.get("severity"), "score": round(score(f), 2), "title": f.get("title", "")[:100]} for f in top],
            "metrics": len(flatten(run["metrics"]))}


def diff(cur, prev):
    C = {fp_of(f): f for f in cur["findings"]}
    P = {fp_of(f): f for f in prev["findings"]}
    out = {"new": [], "resolved": [], "regressed": [], "improved": [], "unchanged": []}
    for k in sorted(set(C) - set(P)):
        out["new"].append(C[k])
    for k in sorted(set(P) - set(C)):
        out["resolved"].append(P[k])
    for k in sorted(set(C) & set(P)):
        c, p = C[k], P[k]
        dc, dp = SEV.get(c.get("severity"), 9), SEV.get(p.get("severity"), 9)
        if dc < dp or (dc == dp and c.get("impact", 0) > p.get("impact", 0)):
            out["regressed"].append(c)
        elif dc > dp or (dc == dp and c.get("impact", 0) < p.get("impact", 0)):
            out["improved"].append(c)
        else:
            out["unchanged"].append(c)
    res = {k: [{"id": f.get("id"), "severity": f.get("severity"), "fingerprint": fp_of(f), "title": f.get("title", "")[:100]} for f in v]
           for k, v in out.items()}
    for f in res["regressed"] + res["improved"]:
        f["was"] = P[f["fingerprint"]].get("severity")
    mc, mp = flatten(cur["metrics"]), flatten(prev["metrics"])
    res["metric_deltas"] = {k: {"prev": mp.get(k), "cur": mc.get(k), "delta": (mc[k] - mp[k]) if k in mc and k in mp else None}
                            for k in sorted(set(mc) | set(mp)) if mc.get(k) != mp.get(k)}
    bc, bp = flatten(cur["baseline"].get("counts", {})), flatten(prev["baseline"].get("counts", {}))
    res["baseline_count_deltas"] = {k: {"prev": bp.get(k), "cur": bc.get(k)} for k in sorted(set(bc) | set(bp)) if bc.get(k) != bp.get(k)}
    hc, hp = cur["baseline"].get("config_sha256_prefix", {}), prev["baseline"].get("config_sha256_prefix", {})
    res["config_hash_changed"] = sorted(k for k in set(hc) | set(hp) if (hc.get(k) or {}).get("sha") != (hp.get(k) or {}).get("sha"))
    if cur["mcp"] and prev["mcp"]:
        r = subprocess.run([sys.executable, "-I", MCPH, "diff", prev["mcp"], cur["mcp"], "--json"], capture_output=True, text=True)
        res["mcp"] = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {"error": r.stderr[-200:]}
    else:
        res["mcp"] = {"skipped": "baseline-mcp-tools.json missing in one run"}
    res["counts"] = {k: len(res[k]) for k in ("new", "resolved", "regressed", "improved", "unchanged")}
    return res


def md_summary(s):
    L = [f"# Run summary: {s['run']}", "", f"Findings: {s['findings']} ({s['findings_file']})  ",
         "By severity: " + ", ".join(f"{k} {v}" for k, v in s["by_severity"].items()), "",
         "| ID | Sev | Score | Title |", "|---|---|---|---|"]
    L += [f"| {f['id']} | {f['severity']} | {f['score']} | {f['title']} |" for f in s["top10"]]
    L += ["", f"Metrics recorded: {s['metrics']}"]
    return "\n".join(L) + "\n"


def md_diff(d, cur, prev):
    L = [f"# Diff: {cur} vs {prev}", "", "| Bucket | Count |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in d["counts"].items()]
    for k in ("new", "regressed", "resolved", "improved"):
        if d[k]:
            L += ["", f"## {k.capitalize()}"]
            L += [f"- {f['id']} {f.get('was', '') + '->' if f.get('was') else ''}{f['severity']}: {f['title']}" for f in d[k]]
    if d["metric_deltas"]:
        L += ["", "## Metric deltas", "| Metric | Prev | Cur | Delta |", "|---|---|---|---|"]
        L += [f"| {k} | {v['prev']} | {v['cur']} | {v['delta']} |" for k, v in d["metric_deltas"].items()]
    if d["baseline_count_deltas"]:
        L += ["", "## Baseline count deltas"] + [f"- {k}: {v['prev']} -> {v['cur']}" for k, v in d["baseline_count_deltas"].items()]
    if d["config_hash_changed"]:
        L += ["", "## Config files changed (hash only)"] + [f"- {k}" for k in d["config_hash_changed"]]
    m = d["mcp"]
    L += ["", "## MCP tool definitions"]
    if m.get("changed"):
        for k in ("servers_added", "servers_removed", "instructions_changed"):
            if m.get(k): L.append(f"- {k}: {', '.join(m[k])}")
        for k in ("tools_added", "tools_removed", "desc_changed", "schema_changed"):
            for s, ts in (m.get(k) or {}).items():
                L.append(f"- {k} [{s}]: {', '.join(ts[:12])}")
        for s, mm in (m.get("new_flags") or {}).items():
            for t, fl in mm.items():
                L.append(f"- new_flags [{s}] {t}: {', '.join(fl)}")
    else:
        L.append(f"- {m.get('skipped') or m.get('error') or 'no changes'}")
    return "\n".join(L) + "\n"


def selftest():
    fx = os.path.join(HERE, "fixtures", "report")
    a, b = load(os.path.join(fx, "run-a")), load(os.path.join(fx, "run-b"))
    d = diff(b, a)
    s = summary(b)
    md = md_diff(d, "run-b", "run-a")
    checks = {
        "counts": d["counts"] == {"new": 1, "resolved": 1, "regressed": 1, "improved": 1, "unchanged": 1},
        "new_is_HK": [f["id"] for f in d["new"]] == ["HK-001"],
        "resolved_is_SEC": [f["id"] for f in d["resolved"]] == ["SEC-001"],
        "regressed_P1_to_P0": d["regressed"][0]["id"] == "MCP-001" and d["regressed"][0]["was"] == "P1",
        "metric_delta": d["metric_deltas"].get("scores.MCP", {}).get("delta") == 2 and d["metric_deltas"]["cost.usd_30d"]["delta"] == -585,
        "baseline_count_delta": d["baseline_count_deltas"] == {"skills_agents": {"prev": 97, "cur": 99}},
        "config_hash_changed": d["config_hash_changed"] == [".claude/settings.json"],
        "mcp_desc_changed": d["mcp"].get("desc_changed") == {"web": ["fetch"]},
        "summary_top": s["top10"][0]["id"] == "MCP-001" and s["findings"] == 4,
        "fingerprint_stable": fingerprint("MCP", os.path.expanduser("~/.claude/settings.json:12"), "Unpinned @latest")
                              == fingerprint("mcp", "~/.claude/settings.json", "unpinned-latest"),
        "fingerprint_len": len(fingerprint("a", "b", "c")) == 16,
        "markdown_has_sections": "## Regressed" in md and "## MCP tool definitions" in md,
    }
    bad = [k for k, v in checks.items() if not v]
    emit("".join(f"{'ok' if v else 'FAIL'} {k}\n" for k, v in checks.items()))
    emit(f"report.py selftest {'PASS' if not bad else 'FAIL'} ({len(checks) - len(bad)}/{len(checks)})\n")
    return 0 if not bad else 1


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        emit(__doc__); return 0
    if argv[0] == "--selftest":
        return selftest()
    if argv[0] == "--fingerprint" and len(argv) == 4:
        emit(fingerprint(*argv[1:]) + "\n"); return 0
    run = load(argv[0])
    as_json = "--json" in argv
    if "--diff" in argv:
        prev_dir = argv[argv.index("--diff") + 1]
        d = diff(run, load(prev_dir))
        emit(json.dumps(d, indent=1) + "\n" if as_json else md_diff(d, argv[0], prev_dir))
    else:
        s = summary(run)
        emit(json.dumps(s, indent=1) + "\n" if as_json else md_summary(s))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
