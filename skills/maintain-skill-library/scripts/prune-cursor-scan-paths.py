#!/usr/bin/env python3
"""Report duplicate skill aliases; archive only an explicitly approved selection.

Personal skills live in ~/.agents/skills. Keep Cursor sync aliases, system skills,
plugin caches, app-owned links, and real directories with possible local changes.
The scheduled updater runs this script without --apply and makes no retirements.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
from pathlib import Path

HOME = Path.home()
AGENTS = HOME / '.agents/skills'
CURSOR = HOME / '.cursor/skills'
CODEX = HOME / '.codex/skills'
CLAUDE = HOME / '.claude/skills'


def candidates() -> list[Path]:
    """Only broken links or redundant aliases are safe automatic candidates."""
    found = []
    canonical = AGENTS.resolve()
    for view in (CURSOR, CODEX, CLAUDE):
        if not view.is_dir():
            continue
        for path in sorted(view.iterdir()):
            if path.name.startswith('.') or not path.is_symlink():
                continue
            try:
                target = path.resolve()
            except (OSError, RuntimeError):
                # A loop or inaccessible target needs manual diagnosis.
                continue
            if not path.exists():
                found.append(path)
            elif view != CURSOR and target.is_relative_to(canonical):
                found.append(path)
    return found


def archive(paths: list[Path], *, allow_bulk: bool = False) -> Path | None:
    """Move aliases only after authorization; never overwrite an existing archive."""
    if len(paths) >= 20 and not allow_bulk:
        raise ValueError('20+ moves require explicit bulk approval and --allow-bulk')
    if not paths:
        return None
    current = set(candidates())
    if any(path not in current for path in paths):
        raise ValueError('Skill aliases changed; review a fresh plan before applying')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H%M%S.%fZ')
    dest = HOME / '.agents/skill-archive' / f'{stamp}-approved-aliases'
    dest.mkdir(parents=True, exist_ok=False)
    manifest = []
    for path in paths:
        target = dest / path.parent.parent.name / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
        manifest.append(f'{path} -> {target}')
        # Keep recovery information even if a later move fails.
        (dest / 'MANIFEST.txt').write_text('\n'.join(manifest) + '\n')
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Archive reviewed aliases after user authorization')
    parser.add_argument('--allow-bulk', action='store_true', help='Confirm separate authorization for 20+ moves')
    args = parser.parse_args(argv)
    paths = candidates()
    print(f'{len(paths)} skill alias(es) eligible for retirement')
    for path in paths:
        print(path)
    if not args.apply:
        print('Read-only scan; no files moved. Preserve real directories for manual review.')
        return 0
    try:
        dest = archive(paths, allow_bulk=args.allow_bulk)
    except (OSError, ValueError) as exc:
        print(f'Retirement stopped: {exc}')
        return 1
    print(f'Archived {len(paths)} aliases to {dest}' if dest else 'Nothing to archive')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
