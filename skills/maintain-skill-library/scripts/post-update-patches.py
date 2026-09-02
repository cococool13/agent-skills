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
GROK_SKILLS = HOME / ".grok" / "skills"
BIN = HOME / ".local" / "bin"
LOG: list[str] = []


def log(msg: str) -> None:
    LOG.append(msg)
    print(msg)


def materialize_ego_browser() -> None:
    """Keep ~/.agents/skills/ego-browser as a real directory, never the app bundle."""
    dest = AGENTS / "ego-browser"
    if not dest.exists() and not dest.is_symlink():
        return
    if dest.is_symlink():
        resolved = dest.resolve()
        tmp = AGENTS / ".ego-browser-real"
        if tmp.exists():
            shutil.rmtree(tmp)
        shutil.copytree(resolved, tmp, symlinks=False)
        dest.unlink()
        tmp.rename(dest)
        log(f"materialized ego-browser off {resolved}")


def prune_grok_skill_duplicates() -> None:
    """Grok already scans ~/.agents/skills via [skills].paths. Do not keep copies here."""
    GROK_SKILLS.mkdir(parents=True, exist_ok=True)
    readme = GROK_SKILLS / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Grok user skills\n\n"
            "Do not put skill copies here.\n\n"
            "Grok loads `~/.agents/skills` via `[skills].paths` in `~/.grok/config.toml`.\n"
        )
    count = 0
    for p in list(GROK_SKILLS.iterdir()):
        if p.name in {"README.md", ".DS_Store"}:
            continue
        if p.is_symlink():
            p.unlink()
            count += 1
        elif p.is_dir() and (p / "SKILL.md").exists():
            # Never rm. Leave real dirs; the prune script archives Cursor dupes.
            log(f"left real dir in ~/.grok/skills: {p.name}")
    if count:
        log(f"removed {count} duplicate ~/.grok/skills symlink(s)")


def install_ego_browser_wrapper() -> None:
    src = OVERLAYS / "ego-browser" / "scripts" / "ego-browser-wrapper.sh"
    if not src.is_file():
        return
    BIN.mkdir(parents=True, exist_ok=True)
    dest = BIN / "ego-browser"
    if dest.is_symlink():
        dest.unlink()
    shutil.copy2(src, dest)
    dest.chmod(0o755)
    log(f"installed ego-browser wrapper at {dest}")


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
    materialize_ego_browser()
    apply_ego_browser_description()
    merge_ego_browser_learnings()
    prune_grok_skill_duplicates()
    install_ego_browser_wrapper()
    sync_cleanup_downloads()
    if not LOG:
        log("(no overlay patches applied)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
