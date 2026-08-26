---
name: ship
description: Slash-only current-repo ship. Use when Cohen runs /ship or asks to commit, push, and deploy the project this session is working in.
disable-model-invocation: true
---

# Ship

Slash `/ship` is the approval. Run immediately. Do not re-plan by hand.

Scope is the current git repo only. Do not fetch, commit, merge, push, clean, or deploy any other repo. Do not update the skill library.

```bash
python3 ~/.agents/skills/ship/scripts/ship.py --apply
```

That fetches this repo, trashes stale owned worktrees here, classifies dirty files, merge-previews leftover branches, then **itself** commits, merges clean leftovers onto `main`, rebases/ff, and pushes.

If cwd is not a git repo, stop. Do not housekeep elsewhere.

Exit: `0` git done, `2` work remains (usually deploy), `1` a git step failed.

## Hard stops

- Never force-push, `--no-verify`, or amend unless Cohen asked.
- Never print secret values. Never stage `skip-files`.
- Never delete a KEEP ref or a dirty/unique worktree.
- Never permanently delete — Trash only.
- Never bare `wrangler deploy` on a named-env Worker.
- Never assume Vercel. Read this repo's `CLAUDE.md`, then `deploy-cloudflare`.
- On failure: do not retry push/deploy.

## After the script

The script does not deploy. You do:

1. If the plan has `deploy`: `mode=ci` after a `main` push → report CI, do not also wrangler. `mode=manual` → this repo's `CLAUDE.md` + `deploy-cloudflare`, then `ego-browser` on the live URL. If ego-browser cannot connect, say so and stop verifying. The script does not plan deploy when `CLAUDE.md` says the repo is not a deploy target, or when there is no wrangler/Firebase/CI deploy surface.
2. Re-run `ship.py --plan-only --skip-fetch`. Remaining git ops mean the apply pass failed — fix those, do not ignore them. KEEP refs stay.

## Report

- **Shipped** — this repo, commit, push, deploy (CI vs wrangler vs skipped), URL
- **Cleaned** — commits/merges/pushes the script applied, worktrees trashed here
- **Still open** — KEEP refs, secrets/noise left, local-only, failures
