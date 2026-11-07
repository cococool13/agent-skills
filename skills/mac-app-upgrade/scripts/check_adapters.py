#!/usr/bin/env python3
"""Report which optional adapters and tools mac-app-upgrade can use on this machine.

Read-only. Prints JSON (or writes it with --out). For each adapter it gives the
SKILL.md path and how to use it:
  "skill"     - callable with the agent's Skill tool
  "read-file" - installed but slash-only (disable-model-invocation); read the
                SKILL.md at `path` and follow it, or ask the user to run `/<plugin>:<name>`
  "missing"   - skip it; do not fake it
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
SKILL_DIRS = [HOME / ".claude/skills", HOME / ".agents/skills", HOME / ".codex/skills"]
PLUGIN_CACHE = HOME / ".claude/plugins/cache"

# name -> plugin that ships it (None = plain skill folder)
ADAPTERS = {
    "repo-upgrade": None,
    "security-audit": None,
    "ponytail-review": None,
    "tdd": None,
    "diagnosing-bugs": None,
    "swiftui-expert-skill": None,
    "swift-concurrency": None,
    "swiftdata-pro": None,
    "swift-testing-pro": None,
    "axiom-accessibility": None,
    "axiom-storekit": None,
    "xcode-build-orchestrator": None,
    "statechart": "pstack",
    "blast-radius": "pstack",
    "interrogate": "pstack",
    "arena": "pstack",
    "create-formal-verification-skill": "pstack",
}
TOOLS = ["git", "python3", "node", "bun", "mise", "java", "xcodebuild", "swiftlint", "periphery", "codesign", "spctl"]


def version_key(p: Path) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", p.name))


def plugin_skill(plugin: str, name: str) -> Path | None:
    hits = [p for p in PLUGIN_CACHE.glob(f"*/{plugin}/*") if (p / "skills" / name / "SKILL.md").is_file()]
    if not hits:
        return None
    return max(hits, key=version_key) / "skills" / name / "SKILL.md"


def find(name: str, plugin: str | None) -> dict:
    path = None
    if plugin:
        path = plugin_skill(plugin, name)
    else:
        for d in SKILL_DIRS:
            if (d / name / "SKILL.md").is_file():
                path = d / name / "SKILL.md"
                break
    if path is None:
        return {"use": "missing"}
    head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    slash_only = re.search(r"^disable-model-invocation:\s*true", head, re.M) is not None
    entry = {"use": "read-file" if slash_only else "skill", "path": str(path.resolve())}
    if plugin:
        entry["slash"] = f"/{plugin}:{name}"
    return entry


def tool(name: str) -> str | None:
    where = shutil.which(name)
    if not where:
        return None
    try:
        out = subprocess.run([where, "--version"], capture_output=True, text=True, timeout=10)
        first = (out.stdout or out.stderr).strip().splitlines()
        return first[0] if first else where
    except (OSError, subprocess.TimeoutExpired):
        return where


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    report = {
        "adapters": {n: find(n, p) for n, p in ADAPTERS.items()},
        "tools": {t: tool(t) for t in TOOLS},
    }
    sc = report["adapters"]["statechart"]
    if sc.get("path"):
        report["statechartCommand"] = str(Path(sc["path"]).parent / "scripts" / "statechart")
        report["statechartReady"] = bool(report["tools"]["mise"]) and bool(
            report["tools"]["node"] or report["tools"]["bun"]
        )
    payload = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
