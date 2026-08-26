---
name: maintain-skill-library
description: "Use when auditing, cleaning up, optimizing, documenting, or validating an installed skill collection, especially when triggers overlap or the user asks about all skills."
---

# Maintain Skill Library

Keep the live skill system predictable, lean, and safe to update.

## 1. Establish ownership

Inventory every `SKILL.md` in `~/.agents/skills`, `~/.claude/skills`,
`~/.cursor/skills`, `~/.codex/skills`, enabled plugin roots, and any
project-local skill roots. Use `~/.agents/.skill-lock.json` to distinguish
source-managed installs from original personal skills.

`~/.agents/skills` is the canonical store for shared personal and source-managed
skills. Cursor discovers that folder natively. Codex-only skills live in
`~/.codex/skills.parked-not-for-cursor` so they do not load in every Cursor chat.
Do not also install the same `SKILL.md` into `~/.cursor/skills`,
`~/.claude/skills`, or `~/.codex/skills` — Cursor scans all four. Cursor
built-ins (`~/.cursor/skills-cursor`) and plugin caches stay untouched.

After `npx skills update`, run
`scripts/prune-cursor-scan-paths.py` so the CLI cannot re-spread copies into
the extra scan paths. Weekly LaunchAgent `com.cococool.skills-update` runs
`scripts/update-skills.sh` (update then prune). Original personal skills have
no upstream and do not auto-update.

Classify each package as original personal, source-managed install, Codex
system/curated, plugin-managed, or project-local. This step is complete when every
live package has one source classification and duplicate names are accounted for.

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

Rerun the inventory and structural checks against the installed paths, inspect the
exact before/after diff, and smoke-test changed routing with representative positive
and negative prompts. Produce a catalog with each skill's name, source, invocation
mode, and plain-language use case.

Complete the maintenance run only when changed skills pass validation, every local
pointer resolves, the catalog count matches the live inventory, and any provider-
managed defects are separated from actionable personal changes.
