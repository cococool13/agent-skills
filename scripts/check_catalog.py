#!/usr/bin/env python3
"""Catalog metadata check: skill frontmatter fields and catalog/third-party.yaml.

Every skills/<name>/SKILL.md carries, next to `name` and `description`:
  when:     one short phrase, when to reach for the skill (at most 90 characters, no final period)
  category: one of CATEGORIES
  level:    one of LEVELS
  setup:    "none" or "<N> min", optionally followed by "; <requirement>"

catalog/third-party.yaml lists third-party skills, credited and linked, never re-hosted:
  skills:
    - name: "<skill name>"          required
      purpose: "<one line>"          required, from the skill's own description
      author: "<author or org>"      optional
      source: "<https URL>"          required; "unknown" when nothing states an origin

Standard library only. Exit 1 with one line per problem.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CATEGORIES = ("design", "code", "audit", "ship", "research", "writing", "setup")
LEVELS = ("beginner", "intermediate", "advanced")
FIELDS = ("when", "category", "level", "setup")
SETUP_RE = re.compile(r"^(none|[1-9]\d* min)(; \S.*)?$")
WHEN_MAX = 90
THIRD_PARTY_KEYS = {"name": True, "purpose": True, "author": False, "source": True}
PRIVATE_RE = re.compile(r"cohen|coolidge|cococool|[\w.+-]+@[\w-]+\.\w|~/|/Users/", re.I)


def frontmatter(text: str) -> dict[str, str]:
    """Top-level scalar keys of a SKILL.md frontmatter block (not a full YAML parser)."""
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError("unterminated frontmatter")
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if m:
            data[m.group(1)] = unquote(m.group(2).strip())
    return data


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def check_skill(name: str, text: str) -> list[str]:
    try:
        fm = frontmatter(text)
    except ValueError as exc:
        return [f"{name}: {exc}"]
    problems = []
    for key in FIELDS:
        if not fm.get(key):
            problems.append(f"{name}: missing `{key}`")
    when = fm.get("when", "")
    if when and (len(when) > WHEN_MAX or when.endswith(".")):
        problems.append(f"{name}: `when` must be one phrase of at most {WHEN_MAX} characters with no final period")
    if fm.get("category") and fm["category"] not in CATEGORIES:
        problems.append(f"{name}: category `{fm['category']}` is not one of {', '.join(CATEGORIES)}")
    if fm.get("level") and fm["level"] not in LEVELS:
        problems.append(f"{name}: level `{fm['level']}` is not one of {', '.join(LEVELS)}")
    if fm.get("setup") and not SETUP_RE.match(fm["setup"]):
        problems.append(f"{name}: setup `{fm['setup']}` must be `none` or `<N> min`, optionally `; <requirement>`")
    return problems


def check_skills(skills_root: Path) -> list[str]:
    problems = []
    dirs = sorted(p for p in skills_root.iterdir() if p.is_dir())
    if not dirs:
        return [f"{skills_root}: no skills found"]
    for d in dirs:
        f = d / "SKILL.md"
        if not f.exists():
            problems.append(f"{d.name}: missing SKILL.md")
            continue
        problems += check_skill(d.name, f.read_text())
    return problems


def parse_third_party(text: str) -> list[dict[str, str]]:
    """Parse the fixed third-party.yaml shape: a `skills:` list of flat string maps."""
    entries: list[dict[str, str]] = []
    seen_root = False
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line == "skills:":
            if seen_root:
                raise ValueError(f"line {n}: duplicate `skills:`")
            seen_root = True
            continue
        if not seen_root:
            raise ValueError(f"line {n}: expected `skills:` first")
        m = re.match(r"^  - ([a-z]+):\s*(.+)$", line) or re.match(r"^    ([a-z]+):\s*(.+)$", line)
        if not m:
            raise ValueError(f"line {n}: not a `key: value` entry line")
        key, value = m.group(1), unquote(m.group(2).strip())
        if line.startswith("  - "):
            entries.append({})
        elif not entries:
            raise ValueError(f"line {n}: field outside an entry")
        if key in entries[-1]:
            raise ValueError(f"line {n}: duplicate `{key}`")
        entries[-1][key] = value
    if not seen_root:
        raise ValueError("missing `skills:`")
    return entries


def check_third_party(text: str, own_skills: set[str]) -> list[str]:
    try:
        entries = parse_third_party(text)
    except ValueError as exc:
        return [f"third-party.yaml: {exc}"]
    if not entries:
        return ["third-party.yaml: no entries"]
    problems, names = [], set()
    for i, e in enumerate(entries, 1):
        label = e.get("name") or f"entry {i}"
        for key, required in THIRD_PARTY_KEYS.items():
            if required and not e.get(key):
                problems.append(f"third-party.yaml: {label}: missing `{key}`")
        for key in e.keys() - THIRD_PARTY_KEYS.keys():
            problems.append(f"third-party.yaml: {label}: unknown key `{key}`")
        src = e.get("source", "")
        if src and src != "unknown" and not re.match(r"^https://\S+$", src):
            problems.append(f"third-party.yaml: {label}: source must be an https URL or `unknown`")
        name = e.get("name", "")
        if name in names:
            problems.append(f"third-party.yaml: {label}: duplicate name")
        if name in own_skills:
            problems.append(f"third-party.yaml: {label}: is a skill in this repo, not third-party")
        names.add(name)
        if any(PRIVATE_RE.search(v) for v in e.values()):
            problems.append(f"third-party.yaml: {label}: contains a personal name, email or local path")
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    skills_root = root / "skills"
    problems = check_skills(skills_root)
    own = {p.name for p in skills_root.iterdir() if p.is_dir()}
    tp = root / "catalog" / "third-party.yaml"
    if tp.exists():
        problems += check_third_party(tp.read_text(), own)
    else:
        problems.append("catalog/third-party.yaml: missing")
    for p in problems:
        print(p)
    if problems:
        return 1
    print(f"catalog ok: {len(own)} skills, {len(parse_third_party(tp.read_text()))} third-party entries")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
