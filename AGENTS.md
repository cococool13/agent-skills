# agent-skills

Personal agent skills library. Installed to `~/.agents/skills` via the skills CLI.

## Commands

```bash
npx skills add cococool13/agent-skills --all -g -y
python3 skills/maintain-skill-library/scripts/post-update-patches.py
python3 -m unittest discover -s skills/ship/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/maintain-skill-library/scripts -p 'test_*.py'
```

## Structure

- `skills/<name>/SKILL.md` — one folder per skill
- Edit `skills/` in this checkout. After authorized publication, run the update workflow in `skills/maintain-skill-library/SKILL.md`; the local LaunchAgent runs daily at 10:00.

Not a deploy target. No wrangler.

Read `~/.agents/AGENTS.md` for shared rules. Source edits belong in `skills/`; follow `maintain-skill-library` to preserve local adaptations. Publishing changes requires explicit authorization.
