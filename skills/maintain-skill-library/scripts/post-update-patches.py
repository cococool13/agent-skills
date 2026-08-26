#!/usr/bin/env python3
"""Apply local overlays after `npx skills update`. Never rm — merge or copy only."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

HOME = Path.home()
AGENTS = HOME / ".agents" / "skills"
OVERLAYS = HOME / ".agents" / "skill-overlays"
SCRIPTS = HOME / "scripts"
LOG: list[str] = []


def log(msg: str) -> None:
    LOG.append(msg)
    print(msg)


def apply_ego_browser_description() -> None:
    skill = AGENTS / "ego-browser" / "SKILL.md"
    overlay = OVERLAYS / "ego-browser" / "description.txt"
    if not skill.is_file() or not overlay.is_file():
        return
    text = skill.read_text()
    desc = overlay.read_text().strip()
    new_text, n = re.subn(
        r"(?m)^description:\s*.+$",
        f'description: "{desc}"',
        text,
        count=1,
    )
    if n:
        skill.write_text(new_text)
        log(f"patched ego-browser description ({len(desc)} chars)")


def merge_ego_browser_learnings() -> None:
    src = OVERLAYS / "ego-browser" / "learnings"
    dest = AGENTS / "ego-browser" / "learnings"
    if not src.is_dir() or not (AGENTS / "ego-browser").is_dir():
        return
    count = 0
    for path in src.rglob("*"):
        if path.is_file():
            rel = path.relative_to(src)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or path.read_bytes() != target.read_bytes():
                shutil.copy2(path, target)
                count += 1
    if count:
        log(f"merged {count} ego-browser learning file(s)")


def sync_cleanup_downloads() -> None:
    ref = AGENTS / "organize-mac-files" / "reference" / "cleanup-downloads.sh"
    if not ref.is_file():
        return
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    dest = SCRIPTS / "cleanup-downloads.sh"
    if not dest.exists() or ref.read_bytes() != dest.read_bytes():
        shutil.copy2(ref, dest)
        dest.chmod(0o755)
        log(f"synced {dest}")


def main() -> int:
    apply_ego_browser_description()
    merge_ego_browser_learnings()
    sync_cleanup_downloads()
    if not LOG:
        log("(no overlay patches applied)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
