#!/usr/bin/env python3
"""Static checks for the portable app-upgrade skill package.

This validates package shape (frontmatter, links, required files).
It is not an agent-behavior eval and not a model benchmark.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
REF_RE = re.compile(r"references/([A-Za-z0-9._-]+)")
SCRIPT_RE = re.compile(r"scripts/([A-Za-z0-9._-]+)")


def parse_frontmatter(text: str) -> dict[str, str]:
    m = FM_RE.match(text)
    if not m:
        raise ValueError("SKILL.md is missing YAML frontmatter")
    data: dict[str, str] = {}
    for raw in m.group(1).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if ":" not in raw:
            raise ValueError(f"malformed frontmatter line: {raw}")
        key, val = raw.split(":", 1)
        data[key.strip()] = val.strip().strip('"')
    return data


def iter_linked_names(text: str, pattern: re.Pattern[str]) -> set[str]:
    return set(pattern.findall(text))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="portable skill directory (contains SKILL.md)",
    )
    args = parser.parse_args()
    root: Path = args.skill_root.resolve()
    errors: list[str] = []
    notes: list[str] = []

    skill = root / "SKILL.md"
    if not skill.is_file():
        print(f"ERROR: missing {skill}", file=sys.stderr)
        return 2

    text = skill.read_text(encoding="utf-8")
    lines = text.count("\n") + (0 if text.endswith("\n") else 1)
    if lines > 500:
        errors.append(f"SKILL.md has {lines} lines; keep at or under 500")

    try:
        fm = parse_frontmatter(text)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    name = fm.get("name", "")
    desc = fm.get("description", "")
    if not NAME_RE.fullmatch(name):
        errors.append(f"invalid name {name!r}")
    if name != root.name:
        errors.append(f"name {name!r} does not match directory {root.name!r}")
    if not desc or len(desc) > 1024:
        errors.append(f"description length {len(desc)} must be 1-1024")
    lower = desc.lower()
    if "do not use" not in lower and "not for" not in lower:
        errors.append("description should include non-triggers")

    required_files = [
        "example-invocation.md",
        "PUBLIC-SOURCES.md",
        "scripts/validate_skill.py",
        "scripts/fingerprint_run.py",
        "scripts/parse_invocation.py",
        "scripts/check_adapters.py",
        "scripts/validate_findings.py",
        "references/01-inventory-baseline.md",
        "references/02-threat-model.md",
        "references/03-state-and-verification.md",
        "references/04-journeys.md",
        "references/05-testing-catalog.md",
        "references/06-apple-design-perf.md",
        "references/07-observability-and-ai.md",
        "references/08-review-evidence-adapters.md",
        "references/evidence.schema.json",
    ]
    for rel in required_files:
        if not (root / rel).is_file():
            errors.append(f"missing required file {rel}")

    corpus_parts = [text]
    for path in sorted((root / "references").glob("*")) if (root / "references").is_dir() else []:
        if path.is_file():
            corpus_parts.append(path.read_text(encoding="utf-8", errors="replace"))
    corpus = "\n".join(corpus_parts)

    for rel in iter_linked_names(corpus, REF_RE):
        target = root / "references" / rel
        if not target.is_file():
            errors.append(f"broken reference link references/{rel}")
    for rel in iter_linked_names(corpus, SCRIPT_RE):
        target = root / "scripts" / rel
        if not target.is_file():
            errors.append(f"broken script link scripts/{rel}")

    schema_path = root / "references" / "evidence.schema.json"
    if schema_path.is_file():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            if schema.get("required") != ["schemaVersion", "findings"]:
                errors.append("evidence.schema.json missing required top-level keys")
        except json.JSONDecodeError as exc:
            errors.append(f"evidence.schema.json is not valid JSON: {exc}")

    for phrase in (
        "coverage.md",
        "run-meta.json",
        "STALE",
        "report-only",
        "confirmed-static",
        "references/06-apple-design-perf.md",
        "references/02-threat-model.md",
    ):
        if phrase not in text and phrase not in corpus:
            errors.append(f"expected phrase missing from package: {phrase}")

    if errors:
        print("FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    print("PASS")
    print(f"skill_root={root}")
    print(f"name={name}")
    print(f"description_chars={len(desc)}")
    print(f"skill_md_lines={lines}")
    for note in notes:
        print(f"note: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
