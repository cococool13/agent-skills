#!/usr/bin/env python3
"""repo-upgrade preflight: read-only facts about a repo plus companion-skill paths.

Usage: preflight.py <repo> [--fetch] [--out DIR]   |   preflight.py --selftest
Creates ~/.repo-upgrade/<repo>/run-<N>/ (or --out) with facts.md and facts.json,
and prints the run folder. Never writes inside the target repo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HOME = Path.home()
CACHE = HOME / ".cache/repo-upgrade"
PONYTAIL = ("DietrichGebert/ponytail", "09c434ab73ca43761c5d8b0c5d341926c2fba710")
CLOUDFLARE = ("cloudflare/security-audit-skill", "c1c8a8c1471069fb0e188eeaff69b8e8db6564a8")
TOB = ("trailofbits/skills", "196a9073ab10d35bacf111f945e02c00b2c6883a")
# name -> (repo, pinned sha, folder inside repo); core companions can be fetched.
CORE = {
    "ponytail": (*PONYTAIL, "skills/ponytail"),
    "ponytail-audit": (*PONYTAIL, "skills/ponytail-audit"),
    "ponytail-review": (*PONYTAIL, "skills/ponytail-review"),
    "ponytail-debt": (*PONYTAIL, "skills/ponytail-debt"),
    "security-audit": (*CLOUDFLARE, "skills/security-audit"),
}
OPTIONAL = ["fp-check", "supply-chain-risk-auditor", "agentic-actions-auditor", "variant-analysis",
            "semgrep-rule-creator", "mutation-testing", "post-patch-validation", "differential-review",
            "improve-codebase-architecture", "deslop"]
FLAT_ROOTS = [".agents/skills", ".claude/skills", ".codex/skills", ".cursor/skills", ".grok/skills", ".gemini/skills"]
DEEP_ROOTS = [HOME / ".claude/plugins", HOME / ".grok/installed-plugins", Path("/mnt/skills"), CACHE]
TOOLCHAINS = ["git", "node", "npm", "pnpm", "yarn", "bun", "deno", "python3", "uv", "go", "cargo",
              "swift", "xcodebuild", "ruby", "java", "dotnet"]
SCANNERS = ["knip", "jscpd", "vulture", "deptry", "deadcode", "govulncheck", "cargo-machete", "periphery",
            "osv-scanner", "gitleaks", "trufflehog", "opengrep", "semgrep", "zizmor",
            "actionlint", "pinact", "scc", "lizard", "hyperfine"]
MANIFESTS = {"package.json": "js/ts", "pyproject.toml": "python", "requirements.txt": "python",
             "go.mod": "go", "Cargo.toml": "rust", "Package.swift": "swift", "Gemfile": "ruby",
             "pom.xml": "java", "build.gradle": "java", "build.gradle.kts": "kotlin",
             "wrangler.toml": "cloudflare", "wrangler.jsonc": "cloudflare", "Dockerfile": "docker"}
CONTEXT = ["AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", ".cursor/rules", ".github/pull_request_template.md",
           ".github/copilot-instructions.md", "lefthook.yml", ".pre-commit-config.yaml", ".husky"]


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=120)
    return r.stdout.strip() if r.returncode == 0 else ""


def genuine(skill: Path, name: str) -> bool:
    """Reject look-alikes: security-audit must ship its validators."""
    return name != "security-audit" or (skill.parent / "validate-findings.cjs").is_file()


def find_skill(name: str, repo: Path) -> str | None:
    """User-level roots only: a skill file inside the audited repo is never trusted."""
    repo = repo.resolve()
    extra = [Path(p) for p in os.environ.get("REPO_UPGRADE_SKILL_ROOTS", "").split(":") if p]
    only = os.environ.get("REPO_UPGRADE_ROOTS_ONLY") == "1"
    if name in CORE and not only:
        r, sha, sub = CORE[name]
        extra.append(CACHE / f"{r.replace('/', '__')}@{sha[:12]}" / Path(sub).parent)
    flat = extra if only else extra + [HOME / r for r in FLAT_ROOTS]
    for root in flat:
        skill = (root / name / "SKILL.md")
        if skill.is_file() and genuine(skill, name) and not skill.resolve().is_relative_to(repo):
            return str(skill.resolve())
    for root in [] if only else DEEP_ROOTS:
        if root.is_dir():
            hits = sorted(root.glob(f"**/{name}/SKILL.md"),
                          key=lambda h: (sum(part.startswith(".") for part in h.relative_to(root).parts), len(h.parts)))
            hits = [h for h in hits if genuine(h, name) and not h.resolve().is_relative_to(repo)]
            if hits:
                return str(hits[0].resolve())
    return None


def fetch(name: str) -> str | None:
    repo, sha, sub = CORE[name]
    dest = CACHE / f"{repo.replace('/', '__')}@{sha[:12]}"
    if not dest.is_dir():
        tmp = Path(tempfile.mkdtemp(dir=CACHE.parent if CACHE.parent.is_dir() else None))
        cmds = [["git", "init", "-q", str(tmp)],
                ["git", "-C", str(tmp), "fetch", "-q", "--depth", "1", f"https://github.com/{repo}", sha],
                ["git", "-C", str(tmp), "checkout", "-q", "FETCH_HEAD"]]
        for c in cmds:
            if subprocess.run(c, capture_output=True, timeout=300).returncode:
                shutil.rmtree(tmp, ignore_errors=True)
                return None
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp.rename(dest)
    skill = dest / sub / "SKILL.md"
    return str(skill) if skill.is_file() else None


def gate_commands(repo: Path) -> list[str]:
    cmds = []
    pkg = repo / "package.json"
    if pkg.is_file():
        try:
            scripts = json.loads(pkg.read_text()).get("scripts", {})
        except (ValueError, OSError):
            scripts = {}
        runner = "pnpm" if (repo / "pnpm-lock.yaml").exists() else "bun run" if (repo / "bun.lockb").exists() or (repo / "bun.lock").exists() else "yarn" if (repo / "yarn.lock").exists() else "npm run"
        cmds += [f"{runner} {s}" for s in scripts if re.fullmatch(r"(test|lint|typecheck|type-check|check|verify|gate|ci)(:.*)?", s)]
    if (repo / "pyproject.toml").is_file() or (repo / "pytest.ini").is_file():
        cmds.append("python3 -m pytest -q")
    if (repo / "go.mod").is_file():
        cmds += ["go vet ./...", "go test ./..."]
    if (repo / "Cargo.toml").is_file():
        cmds += ["cargo clippy --all-targets", "cargo test"]
    if (repo / "Package.swift").is_file():
        cmds.append("swift test")
    for mk in ("Makefile", "justfile"):
        f = repo / mk
        if f.is_file():
            tool = "make" if mk == "Makefile" else "just"
            cmds += [f"{tool} {t}" for t in re.findall(r"^(test|lint|check|verify|gate|ci)\s*:", f.read_text(errors="ignore"), re.M)]
    return cmds


def facts(repo: Path, do_fetch: bool) -> dict:
    files = git(repo, "ls-files").splitlines()
    sizes = []
    for f in files:
        try:
            sizes.append(((repo / f).stat().st_size, f))
        except OSError:
            pass
    shallow = git(repo, "rev-parse", "--is-shallow-repository") == "true"
    churn = []
    if not shallow:
        log = git(repo, "log", "--since=12.months", "--name-only", "--format=")
        tracked = set(files)
        churn = [(f, n) for f, n in Counter(l for l in log.splitlines() if l in tracked).most_common(15)]
    companions = {}
    for name in CORE:
        path = find_skill(name, repo) or (fetch(name) if do_fetch else None)
        companions[name] = path
    return {
        "repo": str(repo), "head": git(repo, "rev-parse", "HEAD"), "branch": git(repo, "branch", "--show-current"),
        "remote": git(repo, "remote", "get-url", "origin"), "shallow": shallow,
        "dirty": len([l for l in git(repo, "status", "--porcelain").splitlines() if l]),
        "recent": git(repo, "log", "--oneline", "-10").splitlines(),
        "files": len(files),
        "by_top": Counter(f.split("/")[0] if "/" in f else "." for f in files).most_common(12),
        "largest": [(f, s) for s, f in sorted(sizes, reverse=True)[:10]],
        "tracked_ignored": git(repo, "ls-files", "-ci", "--exclude-standard").splitlines()[:50],
        "stacks": sorted({v for k, v in MANIFESTS.items() if (repo / k).exists()}
                         | ({"swift"} if any(f.endswith(".xcodeproj/project.pbxproj") for f in files) else set())
                         | ({"github-actions"} if (repo / ".github/workflows").is_dir() else set())),
        "toolchains": [t for t in TOOLCHAINS if shutil.which(t)],
        "gate": gate_commands(repo),
        "context_files": [c for c in CONTEXT if (repo / c).exists()],
        "churn": churn,
        "scanners": [s for s in SCANNERS if shutil.which(s)],
        "companions": companions,
        "optional": {n: find_skill(n, repo) for n in OPTIONAL},
    }


def run_dir(repo: Path, out: str | None, remote: str) -> Path:
    if out:
        d = Path(out).expanduser()
    else:
        parts = re.sub(r"\.git$", "", remote.rstrip("/")).replace(":", "/").split("/")
        if remote and len(parts) >= 2:
            name = f"{parts[-2]}__{parts[-1]}"
        else:  # no remote: directory name plus a short hash of the absolute path
            name = f"{repo.name}__{hashlib.sha256(str(repo.resolve()).encode()).hexdigest()[:8]}"
        base = Path(os.environ.get("REPO_UPGRADE_HOME", HOME / ".repo-upgrade")) / name
        n = 1 + max([int(p.name[4:]) for p in base.glob("run-*") if p.name[4:].isdigit()], default=0)
        d = base / f"run-{n}"
    if d.resolve().is_relative_to(repo.resolve()):
        sys.exit(f"refusing to write inside the target repo: {d}")
    d.mkdir(parents=True, exist_ok=True)
    return d


def markdown(f: dict, prior: list[str]) -> str:
    def rows(items):
        return "\n".join(f"- {a}: {b}" for a, b in items) or "- none"
    missing = [n for n, p in f["companions"].items() if not p]
    lines = [
        f"# Facts: {f['repo']}", "",
        f"- HEAD `{f['head'][:12]}` on `{f['branch'] or 'detached'}`; remote `{f['remote'] or 'none'}`",
        f"- Dirty files: {f['dirty']}; shallow history: {f['shallow']}" + (" (cannot prove an old client never used a route)" if f["shallow"] else ""),
        f"- Tracked files: {f['files']}; stacks: {', '.join(f['stacks']) or 'unknown'}",
        f"- Toolchains here: {', '.join(f['toolchains'])}",
        f"- Prior runs: {', '.join(prior) or 'none'}", "",
        "## Gate commands (detected; confirm against README/CI)", *([f"- `{c}`" for c in f["gate"]] or ["- none detected"]), "",
        "## Companion skills (read by path)", *[f"- {n}: {p or 'MISSING'}" for n, p in f["companions"].items()],
        *([f"- Missing core companions: {', '.join(missing)}. Re-run with --fetch, or use the fallbacks."] if missing else []), "",
        "## Optional companions", *[f"- {n}: {p}" for n, p in f["optional"].items() if p], "- (others not found)", "",
        "## Scanners installed", f"- {', '.join(f['scanners']) or 'none'}", "",
        "## Agent-context and hook files", *([f"- {c}" for c in f["context_files"]] or ["- none"]), "",
        "## Churn hotspots (commits touching file, last 12 months)", rows(f["churn"]), "",
        "## Size by top folder", rows(f["by_top"]), "",
        "## Largest tracked files (bytes)", rows(f["largest"]), "",
        "## Tracked files matching .gitignore", *([f"- {x}" for x in f["tracked_ignored"]] or ["- none"]), "",
        "## Recent commits", *[f"- {c}" for c in f["recent"]], "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", nargs="?")
    ap.add_argument("--fetch", action="store_true", help="clone missing core companions (pinned) into ~/.cache/repo-upgrade")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.repo:
        ap.error("repo is required")
    repo = Path(a.repo).expanduser().resolve()
    if not git(repo, "rev-parse", "--git-dir"):
        sys.exit(f"not a git repository: {repo}")
    f = facts(repo, a.fetch)
    d = run_dir(repo, a.out, f["remote"])
    prior = sorted(p.name for p in d.parent.glob("run-*") if p != d)
    (d / "facts.json").write_text(json.dumps(f, indent=2))
    (d / "facts.md").write_text(markdown(f, prior))
    print(d)
    return 0


def selftest() -> int:
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        repo, home = t / "app", t / "home"
        (repo / "src").mkdir(parents=True)
        (repo / "package.json").write_text(json.dumps({"scripts": {"test": "x", "lint": "y", "dev": "z", "build": "b"}}))
        (repo / "src/a.js").write_text("1")
        (repo / ".gitignore").write_text("dist/\n")
        (repo / "dist").mkdir()
        (repo / "dist/out.js").write_text("2")
        skills = t / "skills/ponytail-audit"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: ponytail-audit\n---\n")
        for c in (["init", "-q"], ["add", "-A"], ["add", "-f", "dist/out.js"],
                  ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
            subprocess.run(["git", "-C", str(repo), *c], check=True, capture_output=True)
        os.environ["REPO_UPGRADE_SKILL_ROOTS"] = str(t / "skills")
        os.environ["REPO_UPGRADE_HOME"] = str(home)
        os.environ["REPO_UPGRADE_ROOTS_ONLY"] = "1"
        f = facts(repo, False)
        assert "js/ts" in f["stacks"], f["stacks"]
        assert f["gate"] == ["npm run test", "npm run lint"], f["gate"]
        assert f["tracked_ignored"] == ["dist/out.js"], f["tracked_ignored"]
        assert f["companions"]["ponytail-audit"].endswith("ponytail-audit/SKILL.md")
        evil = repo / ".claude/skills/ponytail-review"
        evil.mkdir(parents=True)
        (evil / "SKILL.md").write_text("evil")
        os.environ["REPO_UPGRADE_SKILL_ROOTS"] = f"{t / 'skills'}:{repo / '.claude/skills'}"
        assert find_skill("ponytail-review", repo) is None, "trusted a skill inside the target"
        os.environ["REPO_UPGRADE_SKILL_ROOTS"] = str(t / "skills")
        assert ("src/a.js", 1) in f["churn"] or ("package.json", 1) in f["churn"], f["churn"]
        d1, d2 = run_dir(repo, None, ""), run_dir(repo, None, "")
        assert (d1.name, d2.name) == ("run-1", "run-2"), (d1, d2)
        assert run_dir(repo, None, "git@github.com:alice/app.git").parent.name == "alice__app"
        assert run_dir(repo, None, "https://github.com/bob/app").parent.name == "bob__app"
        try:
            run_dir(repo, str(repo / "out"), "")
        except SystemExit:
            pass
        else:
            raise AssertionError("wrote inside target")
        assert "MISSING" in markdown(f, [])  # security-audit not in the temp roots
    print("preflight selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
