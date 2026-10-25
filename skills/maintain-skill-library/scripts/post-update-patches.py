#!/usr/bin/env python3
"""Apply local overlays after `npx skills update`. Never rm — merge or copy only."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

HOME = Path.home()
AGENTS = HOME / ".agents" / "skills"
OVERLAYS = HOME / ".agents" / "skill-overlays"
DESCRIPTIONS = OVERLAYS / "descriptions"
SCRIPTS = HOME / "scripts"
GROK_SKILLS = HOME / ".grok" / "skills"
MAINTENANCE_SOURCE = HOME / "Projects/Agent Skills/skills/maintain-skill-library"
LOG: list[str] = []

# Nested skill path map for description overlays named parent__child.txt
NESTED_SKILL_PATHS: dict[str, Path] = {}


def log(msg: str) -> None:
    LOG.append(msg)
    print(msg)


def restore_local_maintenance() -> None:
    """Keep this user-owned checkout authoritative after an upstream update."""
    dest = AGENTS / "maintain-skill-library"
    if not MAINTENANCE_SOURCE.is_dir() or dest.is_symlink():
        return
    files = [MAINTENANCE_SOURCE / "SKILL.md"]
    files += [p for p in (MAINTENANCE_SOURCE / "scripts").rglob("*")
              if p.is_file() and p.suffix in (".py", ".sh")
              and "__pycache__" not in p.parts]
    files += list((MAINTENANCE_SOURCE / "references").rglob("*.md"))
    changed = 0
    for src in files:
        if not src.is_file():
            continue
        target = dest / src.relative_to(MAINTENANCE_SOURCE)
        if not target.resolve().is_relative_to(dest.resolve()):
            log(f"skip app-owned maintenance path: {target.relative_to(dest)}")
            continue
        if target.resolve() == src.resolve():
            continue
        if target.exists() and target.read_bytes() == src.read_bytes():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        changed += 1
    if changed:
        log(f"restored {changed} local maintenance file(s)")


def prune_grok_skill_duplicates() -> None:
    """Report canonical aliases; preserve app-owned links and require retirement approval."""
    if not GROK_SKILLS.is_dir():
        return
    canonical = AGENTS.resolve()
    aliases = 0
    for path in sorted(GROK_SKILLS.iterdir()):
        if not path.is_symlink():
            continue
        try:
            target = path.resolve()
        except (OSError, RuntimeError):
            log(f"skill link needs review: {path.name}")
            continue
        if target.is_relative_to(canonical):
            aliases += 1
        # Links outside the canonical tree may be app-owned, not duplicate copies.
    if aliases:
        log(f"Grok skill aliases retained: {aliases}")


def _replace_description(skill: Path, desc: str) -> bool:
    """Replace any description form (quoted, folded >, or leftover indented lines)."""
    if not skill.is_file():
        return False
    text = skill.read_text()
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end < 0:
        return False
    fm = text[3:end]
    body = text[end:]
    safe = desc.replace("\\", "\\\\").replace('"', '\\"')
    new_fm, n = re.subn(
        r"(?ms)^description:.*?(?=^[A-Za-z0-9_-]+:|\Z)",
        lambda _: f'description: "{safe}"\n',
        fm,
        count=1,
    )
    if not n:
        return False
    # fm stops before "\n---"; drop the newline the replacement adds so no blank line appears.
    updated = "---" + new_fm.rstrip("\n") + body
    if updated == text:
        return False
    skill.write_text(updated)
    return True


def apply_description_overlays() -> None:
    """Apply short Use-when descriptions from skill-overlays/descriptions/."""
    if not DESCRIPTIONS.is_dir():
        return
    applied = 0
    missing = []
    for path in sorted(DESCRIPTIONS.glob("*.txt")):
        name = path.stem
        desc = path.read_text().strip()
        if not desc:
            continue
        if name in NESTED_SKILL_PATHS:
            skill = NESTED_SKILL_PATHS[name]
        else:
            skill = AGENTS / name / "SKILL.md"
        if skill.parent.is_symlink():
            log(f"skip app-owned description: {name}")
            continue
        if _replace_description(skill, desc):
            applied += 1
            log(f"patched {name} description ({len(desc)} chars)")
        elif not skill.is_file():
            missing.append(name)
    if applied:
        log(f"applied {applied} description overlay(s)")
    if missing:
        log(f"inactive description overlays ({len(missing)}): {', '.join(missing)}")


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



def patch_emil_design_eng_body() -> None:
    """Keep existing local guidance; require review of any reintroduced section."""
    skill = AGENTS / "emil-design-eng" / "SKILL.md"
    if not skill.is_file():
        return
    text = skill.read_text()
    if "## Initial Response" not in text:
        return
    # Heading positions do not prove an approved preimage. Do not erase newly
    # fetched upstream content; move a reviewed exact hunk into instruction-edits.
    raise ValueError('emil-design-eng body changed upstream; review an exact instruction override before continuing')


def main() -> int:
    restore_local_maintenance()
    # Ego CLI and skill are app-owned. Local guidance uses separate source links.
    apply_description_overlays()
    patch_emil_design_eng_body()
    prune_grok_skill_duplicates()
    sync_cleanup_downloads()
    if not LOG:
        log("(no overlay patches applied)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
