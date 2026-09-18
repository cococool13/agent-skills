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
BIN = HOME / ".local" / "bin"
LOG: list[str] = []

# Nested skill path map for description overlays named parent__child.txt
NESTED_SKILL_PATHS = {
    "letsfg__flight-search": AGENTS / "letsfg" / "skills" / "flight-search" / "SKILL.md",
    "letsfg__hotel-search": AGENTS / "letsfg" / "skills" / "hotel-search" / "SKILL.md",
}


def log(msg: str) -> None:
    LOG.append(msg)
    print(msg)


def prune_grok_skill_duplicates() -> None:
    """Report canonical aliases; preserve app-owned links and require retirement approval."""
    if not GROK_SKILLS.is_dir():
        return
    canonical = AGENTS.resolve()
    for path in sorted(GROK_SKILLS.iterdir()):
        if not path.is_symlink():
            continue
        try:
            target = path.resolve()
        except (OSError, RuntimeError):
            log(f"skill link needs review: {path.name}")
            continue
        if target.is_relative_to(canonical):
            log(f"duplicate skill alias retained for review: {path.name}")
        # Links outside the canonical tree may be app-owned, not duplicate copies.


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
    skill.write_text("---" + new_fm + body)
    return True


def apply_ego_browser_description() -> None:
    skill = AGENTS / "ego-browser" / "SKILL.md"
    overlay = OVERLAYS / "ego-browser" / "description.txt"
    if not skill.is_file() or not overlay.is_file():
        return
    desc = overlay.read_text().strip()
    if _replace_description(skill, desc):
        log(f"patched ego-browser description ({len(desc)} chars)")


def apply_description_overlays() -> None:
    """Apply short Use-when descriptions from skill-overlays/descriptions/."""
    if not DESCRIPTIONS.is_dir():
        return
    applied = 0
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
            log(f"skip description overlay (missing skill): {name}")
    if applied:
        log(f"applied {applied} description overlay(s)")


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


def patch_ego_browser_quickstart() -> None:
    """Inject ensureAgentWindow into the installed quick-start heredoc."""
    skill = AGENTS / "ego-browser" / "SKILL.md"
    snippet_path = OVERLAYS / "ego-browser" / "patches" / "ensure-agent-window.js"
    if not skill.is_file() or not snippet_path.is_file():
        return
    text = skill.read_text()
    if "async function ensureAgentWindow" in text:
        return
    snippet = snippet_path.read_text().rstrip() + "\n"
    old = (
        "await openOrReuseTab('https://example.com', { wait: true, timeout: 20 })\n\n"
        "cliLog(await snapshotText())"
    )
    new = (
        "await openOrReuseTab('https://example.com', { wait: true, timeout: 20 })\n"
        "await ensureAgentWindow()\n\n"
        "cliLog(await snapshotText())"
    )
    if old not in text:
        return
    insert_at = text.find("const task = await useOrCreateTaskSpace")
    if insert_at == -1:
        return
    text = text.replace(old, new, 1)
    text = text[:insert_at] + snippet + "\n" + text[insert_at:]
    skill.write_text(text)
    log("patched ego-browser quick start with ensureAgentWindow")



def patch_ego_browser_lean() -> None:
    """Move workflow/caveats to references; condense task-space prose; fix Bash wording."""
    import re
    skill = AGENTS / "ego-browser" / "SKILL.md"
    if not skill.is_file():
        return
    text = skill.read_text()
    changed = False
    refs = skill.parent / "references"
    refs.mkdir(exist_ok=True)
    for header, fname in [
        ("## Recommended workflow", "workflows.md"),
        ("## Caveats", "caveats.md"),
    ]:
        if header not in text:
            continue
        m = re.search(rf"(^{re.escape(header)}\n.*?)(?=^## |\Z)", text, re.M | re.S)
        if not m:
            continue
        (refs / fname).write_text(m.group(1).rstrip() + "\n")
        text = text[: m.start()] + text[m.end() :]
        changed = True
        log(f"ego-browser: extracted {fname}")
    if "Use the `Bash` tool" in text:
        text = text.replace(
            "Use the `Bash` tool to run",
            "Use your shell tool (`Shell` in Cursor) to run",
        )
        changed = True
    if "### Task spaces" in text and "prefer numeric `task.id`" not in text:
        m = re.search(r"(^### Task spaces\n.*?)(?=^### |\Z)", text, re.M | re.S)
        if m:
            new_ts = (
                "### Task spaces\n\n"
                "Isolated browsing context; inherits user login state. "
                "Reuse one space across heredoc rounds via `useOrCreateTaskSpace(nameOrId)` "
                "(prefer numeric `task.id`). New space only for an unrelated goal.\n\n"
                "Ownership: agent / agentDelegatedToUser / user. User-owned spaces: "
                "`switchTaskSpace` throws; `claimTaskSpace` claims; "
                "`handOff`/`complete(..., {keep:true})` skip; "
                "`complete(..., {keep:false})` claims then closes.\n\n"
                "`completeTaskSpace(nameOrId, { keep })` must be its own final heredoc "
                "after the task is confirmed done. Default `{ keep: false }`. "
                "Use `{ keep: true }` only when the user needs the live page.\n\n"
            )
            text = text[: m.start()] + new_ts + text[m.end() :]
            changed = True
            log("ego-browser: condensed Task spaces")
    if "references/workflows.md" not in text and "## Common helpers" in text:
        text = text.replace(
            "## Common helpers\n",
            "## Common helpers\n\n"
            "Details: `references/workflows.md`, `references/caveats.md`, "
            "and Cohen overlay `~/.agents/skill-overlays/ego-browser/references/agents.md`.\n",
            1,
        )
        changed = True
    if changed:
        skill.write_text(text)


def patch_emil_design_eng_body() -> None:
    """Strip canned greeting / promo stall that fights AGENTS execute-first."""
    skill = AGENTS / "emil-design-eng" / "SKILL.md"
    if not skill.is_file():
        return
    text = skill.read_text()
    if "## Initial Response" not in text:
        return
    start = text.find("## Initial Response")
    end = text.find("## The Animation Decision Framework")
    if start < 0 or end < 0:
        return
    replacement = (
        "You are a design engineer with Emil Kowalski craft sensibility. "
        "Build interfaces where unseen details compound. Prefer concrete fixes over philosophy.\n\n"
        "## Review format\n\n"
        "Review findings go in one `Before | After | Why` markdown table, one row per issue.\n\n"
    )
    skill.write_text(text[:start] + replacement + text[end:])
    log("patched emil-design-eng: removed Initial Response stall")


def main() -> int:
    # Ego's app-owned skill follows the installed runtime. Never rewrite that bundle.
    app_owned_ego = (AGENTS / "ego-browser").is_symlink()
    if not app_owned_ego:
        apply_ego_browser_description()
        merge_ego_browser_learnings()
        patch_ego_browser_quickstart()
        patch_ego_browser_lean()
    apply_description_overlays()
    patch_emil_design_eng_body()
    prune_grok_skill_duplicates()
    if not app_owned_ego:
        install_ego_browser_wrapper()
    sync_cleanup_downloads()
    if not LOG:
        log("(no overlay patches applied)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
