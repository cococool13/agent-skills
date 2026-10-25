#!/usr/bin/env python3
"""Read-only shared skill discovery audit. Never inspect credentials or histories."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


def metadata(text: str) -> tuple[str, str]:
    """Read name/description in common SKILL frontmatter, not a full YAML validator."""
    if not text.startswith('---\n') or '\n---' not in text[4:]:
        raise ValueError('missing frontmatter')
    header = text.split('---', 2)[1]
    result = {}
    lines = header.splitlines()
    for i, line in enumerate(lines):
        match = re.match(r'^(name|description):\s*(.*)$', line)
        if not match:
            continue
        key, value = match.groups()
        if value.startswith(('>', '|')):
            parts = []
            for following in lines[i + 1:]:
                if following and not following.startswith((' ', '\t')):
                    break
                parts.append(following.strip())
            value = ' '.join(parts).strip()
        elif value.startswith('"'):
            value = json.loads(value)
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1].replace("''", "'")
        result[key] = value
    if not result.get('name') or not result.get('description'):
        raise ValueError('missing name or description')
    return result['name'], result['description']


BARE_TOOLS = {'Bash', 'Write', 'Edit'}
AGENTS_MD_LIMIT = 9500


def allowed_tools(text: str) -> list[str]:
    """Tool names from `allowed-tools` (inline string/list or YAML list)."""
    if not text.startswith('---\n') or '\n---' not in text[4:]:
        return []
    lines = text.split('---', 2)[1].splitlines()
    for i, line in enumerate(lines):
        match = re.match(r'^allowed-tools:\s*(.*)$', line)
        if not match:
            continue
        value = match.group(1).strip()
        if value:
            return [t.strip().strip('"\'') for t in re.split(r',(?![^(]*\))', value.strip('[]')) if t.strip()]
        tools = []
        for following in lines[i + 1:]:
            item = re.match(r'^\s+-\s*(.+)$', following)
            if not item:
                break
            tools.append(item.group(1).strip().strip('"\''))
        return tools
    return []


def third_party_names(lock: Path) -> set[str]:
    try:
        skills = json.loads(lock.read_text()).get('skills', {})
    except (OSError, ValueError):
        return set()
    return {name for name, entry in skills.items() if not str(entry.get('source', '')).startswith('cococool13/')}


def bare_tool_grants(root: Path, lock: Path) -> list[str]:
    problems = []
    for name in sorted(third_party_names(lock)):
        skill = root / name / 'SKILL.md'
        if not skill.is_file():
            continue
        bare = sorted(BARE_TOOLS.intersection(allowed_tools(skill.read_text())))
        if bare:
            problems.append(f'{name}: third-party allowed-tools grants bare {", ".join(bare)}; strip it with an instruction overlay')
    return problems


def agents_md_size(path: Path) -> list[str]:
    if not path.is_file():
        return []
    size = len(path.read_text())
    return [f'{path}: {size} characters; keep it under {AGENTS_MD_LIMIT}'] if size >= AGENTS_MD_LIMIT else []


def listing_chars(roots: list[Path]) -> int:
    """Characters of the skill listing a client builds: name + description + 4 per skill, once per name."""
    seen = {}
    for root in roots:
        folders = sorted(root.iterdir()) if root.is_dir() else []
        for folder in folders:
            if folder.name.startswith('.'):
                continue
            for skill in [folder / 'SKILL.md', *sorted((folder / 'skills').glob('*/SKILL.md'))]:
                try:
                    name, description = metadata(skill.read_text())
                except (ValueError, OSError):
                    continue
                seen.setdefault(name, len(name) + len(description) + 4)
    return sum(seen.values())


def listing_budget(roots: list[Path], fraction: float, context_tokens: int) -> tuple[int, int, list[str]]:
    """Claude Code lists skills within skillListingBudgetFraction of the context (about 4 chars/token)."""
    used, budget = listing_chars(roots), int(fraction * context_tokens * 4)
    problem = f'skill listing {used} characters exceeds the budget {budget} ({fraction} of {context_tokens} tokens); descriptions get dropped'
    return used, budget, [problem] if used > budget else []


def audit(root: Path, overlays: Path) -> dict:
    rows, errors, warnings = [], [], []
    for folder in sorted(root.iterdir()) if root.is_dir() else []:
        if folder.name.startswith('.'):
            continue
        skill = folder / 'SKILL.md'
        if not skill.is_file():
            continue
        try:
            name, description = metadata(skill.read_text())
        except (ValueError, OSError) as exc:
            errors.append(f'{folder.name}: {exc}')
            continue
        rows.append({'name': name, 'characters': len(description), 'path': str(skill)})
        if len(description) > 220:
            ownership = 'linked/provider' if folder.is_symlink() else 'shared'
            warnings.append(f'{name}: {len(description)} description characters ({ownership})')
    for overlay in sorted(overlays.glob('*.txt')) if overlays.is_dir() else []:
        description = overlay.read_text().strip()
        name = overlay.stem
        if not description or '\n' in description or len(description) > 240:
            errors.append(f'{name}: overlay must be one nonempty line of at most 240 characters')
        target = root / name / 'SKILL.md'
        if '__' in name:
            parent, child = name.split('__', 1)
            target = root / parent / 'skills' / child / 'SKILL.md'
        if not target.is_file():
            warnings.append(f'{name}: inactive overlay; review before reinstalling or archiving')
    return {'skills': len(rows), 'description_characters': sum(r['characters'] for r in rows),
            'errors': errors, 'warnings': warnings, 'entries': rows}


def retired_skill_references(root: Path, rule_roots: list[Path]) -> list[str]:
    problems = []
    for name in ('xcodebuildmcp', 'credential-sweep'):
        if (root / name / 'SKILL.md').is_file():
            continue
        pattern = re.compile(r'(?:[Uu]se|handled by|through)\s+(?:the\s+)?`' + re.escape(name) + r'`\s+skill')
        for rules in rule_roots:
            for path in sorted(rules.iterdir()) if rules.is_dir() else []:
                if path.suffix not in ('.md', '.mdc') or not path.is_file():
                    continue
                if pattern.search(path.read_text()):
                    problems.append(f'{path.name}: instruction routes to missing {name} skill')
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / '.agents/skills')
    parser.add_argument('--overlays', type=Path, default=Path.home() / '.agents/skill-overlays/descriptions')
    parser.add_argument('--lock', type=Path, default=Path.home() / '.agents/.skill-lock.json')
    parser.add_argument('--agents-md', type=Path, default=Path.home() / '.agents/AGENTS.md')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--rules', type=Path, action='append', help='Rule roots; defaults to this user’s Cursor and Claude rules')
    parser.add_argument('--listing-root', type=Path, action='append',
                        help='Skill folders one client lists; defaults to ~/.claude/skills')
    parser.add_argument('--listing-fraction', type=float, default=0.02, help='skillListingBudgetFraction')
    parser.add_argument('--context-tokens', type=int, default=200000, help='Smallest context window in use')
    args = parser.parse_args()
    result = audit(args.root, args.overlays)
    rules = args.rules if args.rules is not None else [Path.home() / '.cursor/rules', Path.home() / '.claude/rules']
    result['errors'].extend(retired_skill_references(args.root, rules))
    result['errors'].extend(bare_tool_grants(args.root, args.lock))
    result['errors'].extend(agents_md_size(args.agents_md))
    listing_roots = args.listing_root or [Path.home() / '.claude/skills']
    used, budget, problems = listing_budget(listing_roots, args.listing_fraction, args.context_tokens)
    result['listing'] = {'characters': used, 'budget': budget}
    result['errors'].extend(problems)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Context audit: {result['skills']} top-level skills; {result['description_characters']} description characters")
        print(f"Skill listing: {used} of {budget} characters")
        for item in result['errors']:
            print('ERROR: ' + item)
        for item in result['warnings']:
            print('REVIEW: ' + item)
        print(f"{len(result['errors'])} errors; {len(result['warnings'])} review items. Read-only; nothing changed.")
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
