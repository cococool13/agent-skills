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
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--rules', type=Path, action='append', help='Rule roots; defaults to this user’s Cursor and Claude rules')
    args = parser.parse_args()
    result = audit(args.root, args.overlays)
    rules = args.rules if args.rules is not None else [Path.home() / '.cursor/rules', Path.home() / '.claude/rules']
    result['errors'].extend(retired_skill_references(args.root, rules))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Context audit: {result['skills']} top-level skills; {result['description_characters']} description characters")
        for item in result['errors']:
            print('ERROR: ' + item)
        for item in result['warnings']:
            print('REVIEW: ' + item)
        print(f"{len(result['errors'])} errors; {len(result['warnings'])} review items. Read-only; nothing changed.")
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
