# agent-skills

Personal agent skills library. Installed to `~/.agents/skills` via the skills CLI.

## Commands

```bash
python3 -m unittest discover -s skills/ship/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/maintain-skill-library/scripts -p 'test_*.py'
python3 skills/maintain-skill-library/scripts/audit-context.py
python3 skills/maintain-skill-library/scripts/apply-instruction-overrides.py --check
```

## Structure

- `skills/<name>/SKILL.md` — one folder per skill
- Edit `skills/` in this checkout. After authorized publication, run the update workflow in `skills/maintain-skill-library/SKILL.md`; the local LaunchAgent runs weekly (Monday 10:00) and updates only pinned lock entries. Guard hooks: edit `scripts/hooks/`, then run `scripts/sync-hooks.sh`.
- Install only reviewed, named skills with the pinned local CLI (`~/.local/share/skills/node_modules/.bin/skills`). Do not install this repository with `--all`: source names `aso`, `refero-design`, `ponytail` and `motion` collide with different installed packages. Compare lock ownership, local overlays and source/install diffs before replacement. A missing lock entry is unknown origin.

Not a deploy target. No wrangler.

Read `~/.agents/AGENTS.md` for shared rules. Source edits belong in `skills/`; follow `maintain-skill-library` to preserve local adaptations. Publishing changes requires explicit authorization.
