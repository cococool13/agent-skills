# Skill description overlays

Short `Use when…` triggers applied after every `npx skills update` by
`post-update-patches.py`.

Why: every installed skill’s name + description is loaded into agent context.
Long, overlapping, or “pick me” descriptions waste budget and cause wrong skill
selection (see pvncher / Astra guidance, 2026-09).

Edit files here as `skill-name.txt` (one line, 140–220 chars; audit-context.py enforces the listing budget). Nested skills
use `parent__child.txt` (e.g. `letsfg__flight-search.txt`).
