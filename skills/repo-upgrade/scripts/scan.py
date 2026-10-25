#!/usr/bin/env python3
"""repo-upgrade scan: run installed scanners in read-only report mode.

Usage: scan.py <repo> <run-dir> [--timeout SEC]   |   scan.py --selftest
Writes <run-dir>/scans/<tool>.txt and scans/summary.md. Hits are leads, not findings.
Never installs anything and never passes a fix/write flag.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# (name, stacks it applies to or None for any, command, install hint, extra condition)
TOOLS = [
    ("knip", {"js/ts"}, ["knip", "--reporter", "json", "--no-exit-code"], "npm i -D knip", None),
    ("jscpd", {"js/ts"}, ["jscpd", ".", "--reporters", "console", "--min-tokens", "50", "--silent",
                          "--ignore", "**/node_modules/**,**/dist/**,**/build/**"], "npm i -D jscpd", None),
    ("vulture", {"python"}, ["vulture", ".", "--min-confidence", "80", "--exclude", ".venv,venv,node_modules"], "pipx install vulture", None),
    ("deptry", {"python"}, ["deptry", "."], "pipx install deptry", None),
    ("deadcode", {"go"}, ["deadcode", "-test", "./..."], "go install golang.org/x/tools/cmd/deadcode@latest", None),
    ("govulncheck", {"go"}, ["govulncheck", "./..."], "go install golang.org/x/vuln/cmd/govulncheck@latest", None),
    ("cargo-machete", {"rust"}, ["cargo-machete", "--with-metadata"], "cargo install cargo-machete", None),
    ("periphery", {"swift"}, ["periphery", "scan", "--quiet"], "brew install periphery", ".periphery.yml"),
    ("osv-scanner", None, ["osv-scanner", "scan", "source", "-r", ".", "--format", "table"], "brew install osv-scanner", None),
    ("gitleaks", None, ["gitleaks", "git", "--redact", "--no-banner", "."], "brew install gitleaks", None),
    ("opengrep", None, ["opengrep", "scan", "--config", ".semgrep", "--text", "."], "see opengrep releases", ".semgrep"),
    ("zizmor", {"github-actions"}, ["zizmor", "--offline", "--min-confidence=medium", ".github/workflows"], "brew install zizmor", None),
    ("actionlint", {"github-actions"}, ["actionlint"], "brew install actionlint", None),
    ("pinact", {"github-actions"}, ["pinact", "run", "--check", "--no-api"], "brew install pinact", None),
    ("scc", None, ["scc", "--no-cocomo"], "brew install scc", None),
    ("lizard", None, ["lizard", "-C", "15", "-w", "-x", "*/node_modules/*", "-x", "*/.venv/*", "."], "pipx install lizard", None),
]


def resolve(repo: Path, name: str) -> str | None:
    local = repo / "node_modules/.bin" / name
    return str(local) if local.is_file() else shutil.which(name)


def detect_stacks(repo: Path) -> set[str]:
    marks = {"package.json": "js/ts", "pyproject.toml": "python", "requirements.txt": "python",
             "go.mod": "go", "Cargo.toml": "rust", "Package.swift": "swift"}
    stacks = {v for k, v in marks.items() if (repo / k).exists()}
    if (repo / ".github/workflows").is_dir():
        stacks.add("github-actions")
    if any(repo.glob("*.xcodeproj")):
        stacks.add("swift")
    return stacks


def scan(repo: Path, run: Path, timeout: int) -> Path:
    out = run / "scans"
    out.mkdir(parents=True, exist_ok=True)
    stacks = detect_stacks(repo)
    ran, missing, skipped = [], [], []
    env = {**os.environ, "NO_COLOR": "1", "CI": "1"}
    for name, applies, cmd, hint, needs in TOOLS:
        if applies and not applies & stacks:
            continue
        if needs and not (repo / needs).exists():
            skipped.append(f"{name} (needs {needs})")
            continue
        exe = resolve(repo, name)
        if not exe:
            missing.append(f"{name}: `{hint}`")
            continue
        try:
            r = subprocess.run([exe, *cmd[1:]], cwd=repo, capture_output=True, text=True, timeout=timeout, env=env)
            text, status = r.stdout + ("\n--- stderr ---\n" + r.stderr if r.stderr.strip() else ""), f"exit {r.returncode}"
        except subprocess.TimeoutExpired:
            text, status = "", f"timeout after {timeout}s"
        (out / f"{name}.txt").write_text(f"$ {' '.join(cmd)}\n{status}\n\n{text}")
        lines = len([l for l in text.splitlines() if l.strip()])
        ran.append(f"| {name} | {status} | {lines} | scans/{name}.txt |")
    summary = ["# Scan summary", "", f"Stacks: {', '.join(sorted(stacks)) or 'unknown'}",
               "Hits are leads. Verify each against source before it becomes a finding.", "",
               "| Tool | Result | Output lines | File |", "| --- | --- | --- | --- |", *(ran or ["| none | | | |"]), "",
               "## Not installed (ask before installing)", *([f"- {m}" for m in missing] or ["- none"]), "",
               "## Skipped", *([f"- {s}" for s in skipped] or ["- none"]), ""]
    (out / "summary.md").write_text("\n".join(summary))
    return out / "summary.md"


def selftest() -> int:
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        repo, run, bindir = t / "app", t / "run", t / "bin"
        (repo / ".github/workflows").mkdir(parents=True)
        (repo / "package.json").write_text("{}")
        bindir.mkdir()
        for name in ("actionlint", "scc"):
            stub = bindir / name
            stub.write_text("#!/bin/sh\necho finding-from-$0 \"$@\"\n")
            stub.chmod(0o755)
        slow = repo / "node_modules/.bin/knip"
        slow.parent.mkdir(parents=True)
        slow.write_text("#!/bin/sh\nsleep 5\n")
        slow.chmod(0o755)
        os.environ["PATH"] = f"{bindir}:/usr/bin:/bin"
        summary = scan(repo, run, timeout=1).read_text()
        assert "| actionlint | exit 0 | 1 |" in summary, summary
        assert "| knip | timeout after 1s |" in summary, summary
        assert "vulture" not in summary  # python tools skipped for a JS repo
        assert "zizmor: `brew install zizmor`" in summary, summary
        assert not any(repo.rglob("*.txt")), "wrote inside target"
    print("scan selftest: ok")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", nargs="?")
    ap.add_argument("run", nargs="?")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.repo and a.run):
        ap.error("repo and run dir are required")
    repo, run = Path(a.repo).expanduser().resolve(), Path(a.run).expanduser().resolve()
    if run.is_relative_to(repo):
        sys.exit(f"refusing to write inside the target repo: {run}")
    print(scan(repo, run, a.timeout))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
