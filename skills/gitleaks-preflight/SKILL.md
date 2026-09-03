---
name: gitleaks-preflight
description: Use before commit, push, or deploy when gitleaks or Cursor secret scans block work. Runs a repo-scoped scan with sensible allowlists.
---

# Gitleaks preflight

Run from the **current git repo root** before push or deploy. Never scan outside this repo.

```bash
bash ~/.agents/skills/gitleaks-preflight/scripts/preflight.sh
```

Exit codes: `0` clean, `1` leaks (fix or allowlist), `2` gitleaks missing.

## First time in a repo

If the repo has no `.gitleaks.toml`:

```bash
bash ~/.agents/skills/gitleaks-preflight/scripts/init-config.sh
git add .gitleaks.toml && git commit -m "chore: add gitleaks allowlists"
```

The template allowlists generated trees, owned worktrees, and **local gitignored secret files** (`.dev.vars`, `Secrets.swift`, `.env*`). Real credentials in tracked files still fail.

## When Cursor blocks deploy

Cursor scans the working tree (like `gitleaks detect --no-git`). A clean `git log` is not enough if gitignored locals contain key-shaped strings.

1. Run preflight in the repo.
2. If hits are gitignored locals → ensure `.gitleaks.toml` path allowlists cover them (init-config adds the standard set).
3. If hits are tracked → remove, rotate, and recommit. Never `--no-verify`.

## With /ship

After `ship.py --apply` and before `wrangler deploy`, run preflight. If it fails, fix allowlists or secrets before deploy — do not retry deploy blindly.

## Report

- Scan mode (git vs working tree)
- Finding count and file paths only — never print secret values
- Whether `.gitleaks.toml` was created or updated
