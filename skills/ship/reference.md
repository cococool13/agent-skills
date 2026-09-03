# Ship reference

`python3 ~/.agents/skills/ship/scripts/ship.py --apply` runs git in the current repo only. `--plan-only` prints without mutating. Default (no flag) still trashes stale owned worktrees here and drops equivalent local branches / superseded stashes / fast-forwards.

Ancestor-of-`main` remotes are skipped before merge-tree.

## File buckets

| Bucket | Rule |
| --- | --- |
| secret | password/credential/token filenames, `.pem` `.key` `.p12`, `.env` `.env.*`, `credentials.json` |
| noise | `.DS_Store`, `__pycache__`, `.uizze/live/`, `*.log`, `*.tsbuildinfo`, `.turbo/`, `coverage/`, owned worktree paths, untracked files over 5 MB |
| archive | untracked files under `_archive/` |
| commit | everything else. Content matching GitHub PAT / AWS key / PEM headers is unstaged even if the name looks safe. |

If unsure, skip and name the type only. Never print secret values.

## Leftover branches

`git merge-tree --write-tree main <ref>` decides leftover branches in this repo — not `branch --no-merged` and not a blind cherry-pick stack.

| Preview | Action |
| --- | --- |
| Clean merge, no file delta vs `main` | Already contained (squash/rewrite). Drop the local branch. |
| Clean merge, real file delta | `git merge --no-edit` into `main`. |
| Conflicts | KEEP. Old cursor/codex branches that would regress `main`. |

Do not `git push --delete` remotes. Do not cherry-pick a long stack of commits that already lost a merge-tree check.

## Worktrees

Owned (this repo only): `<repo>/.claude/worktrees/*`, `.worktrees/*`, `<repo>/worktrees/*`.

Leave `~/.cursor/worktrees`. Always run `git worktree remove` from the main checkout. Unique or dirty trees stay.

## Fast-forward / rebase

`pull.rebase` is on. Never `git pull`.

```bash
git merge --ff-only '@{u}'     # behind only
git rebase '@{u}'              # diverged (ahead and behind)
```

Never `--force`.

## Deploy

Read this repo's `CLAUDE.md`. Use `deploy-cloudflare` for Pages/Workers. Never assume Vercel. Never bare `wrangler deploy` on a named-env Worker.

Before deploy:

```bash
bash ~/.agents/skills/gitleaks-preflight/scripts/preflight.sh
```

If the repo has no `.gitleaks.toml`, run `init-config.sh` first (see `gitleaks-preflight` skill).
