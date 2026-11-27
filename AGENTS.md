# agent-skills

Personal agent skills library. Installed to `~/.agents/skills` via the skills CLI.

## Commands

Checks run on this Mac. `just check` before claiming done (same command as pre-push and `ship`; it runs `scripts/check.sh`, the tests below and gitleaks in parallel); `just check-fast` while working. Never `--no-verify`. Land work only with `.ci/bin/ship`: it checks the exact commit, posts `ci/just-check`, and merges or labels the PR `needs-cohen`. Merging never deploys. After cloning, run `lefthook install` once to get the hooks.

```bash
scripts/check.sh
python3 -m unittest discover -s skills/ship/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/maintain-skill-library/scripts -p 'test_*.py'
python3 skills/repo-upgrade/scripts/preflight.py --selftest && python3 skills/repo-upgrade/scripts/scan.py --selftest
python3 skills/maintain-skill-library/scripts/audit-context.py
python3 skills/maintain-skill-library/scripts/apply-instruction-overrides.py --check
```

## Structure

- `skills/<name>/SKILL.md` — one folder per skill. Besides `name` and `description`, each has catalog fields read by the public skills catalog: `when` (one phrase, at most 90 characters, no final period), `category` (`design`, `code`, `audit`, `ship`, `research`, `writing` or `setup`), `level` (`beginner`, `intermediate` or `advanced`) and `setup` (`none` or `<N> min`, optionally `; <requirement>`). `scripts/check_catalog.py` enforces them.
- `catalog/third-party.yaml` — third-party skills used alongside these, credited and linked, never copied here (`name`, `purpose`, optional `author`, `source` URL or `unknown`). Built from installed skills' frontmatter and the skills lock; leave out anything private.
- Install: `npx skills add cococool13/agent-skills --skill <name>` (several names after one `--skill` work). The skills CLI (1.9.0) has no packs, and in a non-interactive agent session it silently ignores unknown flags such as `--pack` and installs every skill.
- Edit `skills/` in this checkout. After authorized publication, run the update workflow in `skills/maintain-skill-library/SKILL.md`; the local LaunchAgent runs weekly (Monday 10:00) and updates only pinned lock entries. Guard hooks: edit `skills/maintain-skill-library/scripts/hooks/`, then run `skills/maintain-skill-library/scripts/sync-hooks.sh`.
- Install only reviewed, named skills with the pinned local CLI (`~/.local/share/skills/node_modules/.bin/skills`). Third-party skills are installed from their upstream repos, never copied here. Compare lock ownership, local overlays and source/install diffs before replacement. A missing lock entry is unknown origin.

Not a deploy target. No wrangler.

Read `~/.agents/AGENTS.md` for shared rules. Source edits belong in `skills/`; follow `maintain-skill-library` to preserve local adaptations. Publishing changes requires explicit authorization.
