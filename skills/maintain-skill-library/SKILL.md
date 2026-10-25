---
name: maintain-skill-library
description: "Use when auditing or maintaining the installed skill library."
---

# Maintain Skill Library

Keep the live skill system predictable, lean, and safe to update.

Adapt paths and schedule names to your machine. The table below is how the author runs it.

## Example stack (this repo's author)

| Layer | Location | Auto-update |
| --- | --- | --- |
| Personal skills | `cococool13/agent-skills` → `~/.agents/skills` | manual `skills update <name>` |
| Upstream skills | emilkowalski, vercel-labs, uizze, citrolabs, etc. | pinned `ref` (commit sha) in the lock; weekly job applies pinned entries only |
| Local overlays | `~/.agents/skill-overlays/` | `post-update-patches.py` after every update |

Weekly (Monday 10:00): LaunchAgent `com.cococool.skills-update` runs `scripts/update-skills.sh`
from `~/Projects/Agent Skills/skills/maintain-skill-library/` with the pinned CLI in
`~/.local/share/skills` (`skills@1.7.2`; `npm ci` from `skills-cli/`): diff report in
`~/Library/Logs/skills-update/<date>.md` → update of lock entries with a `ref` (no `-y`) →
local overlays → conflict-checked instruction edits → report scan-path duplicates.
`update-skills.sh --dry-run` writes the report and runs the checks only. To take an upstream
change, review it, then move the entry's `ref` (`scripts/skill-refs.py report` / `pin`).
The source checkout and `~/.agents/skill-overlays/instruction-edits.json` preserve
local repairs across upstream updates. An override conflict fails the update and
requires review instead of replacing changed upstream text blindly.
After each update, the overlay restores this checkout's maintenance instructions
and Python/shell scripts to the installed shared skill. Unchanged files are skipped;
app-owned links are preserved. Other skills retain their upstream ownership.

Edit personal skills in your checkout of this repo (author path: `~/Projects/Agent Skills`), push to GitHub, then run the
update script (or the author's weekly job).

## 1. Establish ownership

Inventory every `SKILL.md` in `~/.agents/skills`, `~/.cursor/skills`,
`~/.codex/skills`, `~/.claude/skills`, enabled plugin roots, and any project-local skill roots.
Use `~/.agents/.skill-lock.json` to distinguish source-managed installs from
original personal skills. `~/.claude/skills` is a symlink view of this library, refreshed by `sync-claude-skills.py`.

`~/.agents/skills` is the canonical store for shared personal and source-managed
skills. Cursor discovers that folder natively. Do not install duplicate real copies into client skill folders. Cursor sync
symlinks into the canonical library are intentional aliases, not second copies. Claude Code uses the same kind of alias under `~/.claude/skills`. Cursor built-ins
(`~/.cursor/skills-cursor`) and live plugin caches stay untouched. Scheduled sync
reports real host-specific copies instead of archiving them or exposing them to
other clients. A deliberately host-aware personal skill may share a built-in name.

After `skills update`, run
`scripts/prune-cursor-scan-paths.py` to report extra scan-path copies. Its default
is read-only; apply retirements only with explicit authorization. Preserve app-owned links. Weekly LaunchAgent `com.cococool.skills-update` runs
`scripts/update-skills.sh` (report, pinned update, then scan). Original personal skills have
no upstream and do not auto-update.

The scan includes broken Grok links while preserving working Grok aliases. Shared
guard source is in `scripts/hooks/`. Clients run the installed copies in `~/.agents/hooks/`
(mode 500, `chflags uchg`); `scripts/sync-hooks.sh` copies them only after
`hooks/test_guard.py` passes, and the lefthook pre-commit runs the same test. Run
`python3 -m unittest discover -s scripts -p 'test_*.py'` from this skill's folder
after changing maintenance or hook behavior. `scripts/grok-wrapper.sh` loads the
existing MCP environment before starting Grok; it never prints credential values.

Classify each package as original personal, source-managed install, Codex
system/curated, plugin-managed, or project-local. This step is complete when every
live package has one source classification and duplicate names are accounted for.

## Browser workflow maintenance

Ego CLI and runtime skills are app-owned. Preserve their links and use the
installed TaskSpace/Page API. Local host guidance is maintained in
`references/ego-browser.md`; the overlay reference links to this source.
`scripts/ego-health-check.sh` runs the bounded local fixture check without
restarting the browser or using a public monitoring page.
`scripts/ego-start-performance.sh` starts ego lite with the sampling profilers
off and does nothing when it is already running. Never reinstall the
retired wrapper or legacy helper patches. Run the maintenance test suite after
changing this workflow, and run the live health check when validating Ego.

## 2. Audit predictability

For every package, check frontmatter, folder/name agreement, description length,
local context pointers, stale tool or path assumptions, body size, and trigger
overlap.

For original personal skills, also apply the full authoring rubric from
`writing-great-skills` when it is available: invocation choice, branch boundaries,
completion criteria, progressive disclosure, single source of truth, no-ops, and
positive steering. This step is complete when every structural failure and every
high-confidence routing or execution defect has an owner and disposition.

## 3. Change the smallest useful surface

- Original personal skills: improve within the user's granted scope.
- Source-managed installs: preserve upstream bodies; patch only deliberate local
  adaptations whose update-overwrite tradeoff is understood.
- System and plugin packages: report defects to their provider; keep caches intact.
- Project-local skills: follow the closest `AGENTS.md` and keep project knowledge
  local.

For model-invoked skills, descriptions begin with `Use when` and encode one trigger
per real branch. For user-invoked skills, keep a short human-facing summary and the
manual-invocation marker. Create a new skill only for a recurring cross-project gap
not covered by an existing skill. Keep all retirements reversible and require
explicit approval before deletion or archival.

This step is complete when each edit has a stated behavior change and no managed
package was unintentionally forked.

## 4. Verify the live tree

Run `python3 scripts/audit-context.py` for the read-only top-level discovery
summary and overlay checks. It reports characters, not billed tokens, and
flags verbose provider descriptions for review without rewriting them. It
does not inspect credentials, configuration secrets, or session histories.
It also checks global instruction links/import pointers and reports duplicate
rule bodies, missing adapters and broken links. This verifies files on disk;
fresh client sessions are needed to prove runtime loading.
Keep model-trigger descriptions concise (normally 140–220 characters), with
distinct branches; keep complete execution guidance in the skill body or
references. The scheduled updater runs this check after applying overlays.

Rerun the inventory and structural checks against the installed paths, inspect the
exact before/after diff, and smoke-test changed routing with representative positive
and negative prompts. Produce a catalog with each skill's name, source, invocation
mode, and plain-language use case.

Complete the maintenance run only when changed skills pass validation, every local
pointer resolves, the catalog count matches the live inventory, and any provider-
managed defects are separated from actionable personal changes.
