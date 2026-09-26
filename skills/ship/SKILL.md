---
name: ship
description: "Use when Cohen runs /ship or asks to commit, push, and deploy the current repo only."
disable-model-invocation: true
---

# Ship

`/ship` authorizes commit, push, and deploy for the active project, subject to its `AGENTS.md` and any narrower request. It does not cover App Store submission or review-send, or any step the project marks owner-only or explicit-yes. Ask for those. A request to edit or audit this skill does not authorize shipping.

Work in the current Git checkout only. If cwd is not a repository, stop and name the missing project.

## 1. Plan

Read the project's `AGENTS.md` for build, test, and deploy steps. Then run:

```bash
python3 ~/.agents/skills/ship/scripts/ship.py
```

It fetches the upstream remote and prints JSON: branch, push destination, ahead/behind, staged paths, `buckets`, `pending` operations, and `blockers`. It changes no files.

Buckets exclude files. They do not select them:

- `secret`: `.env*`, `.dev.vars`, keys, credential-like names. Never commit them.
- `noise`: caches, logs, worktrees, untracked files over 5 MB.
- `archive`: untracked `_archive/` content.
- `commit`: everything else. Check the diff for task relevance.

Clear every blocker. If the branch is behind, integrate only the task's changes and keep other branches, stashes, and worktrees intact. Run the project's required build, tests, and checks against the final code, and fix failures.

## 2. Apply

```bash
python3 ~/.agents/skills/ship/scripts/ship.py --apply -m "<type>: <imperative summary>" -m "<trailers>" [path ...]
```

Name the exact paths when the `commit` bucket holds anything unrelated to the task. Without paths, the whole `commit` bucket is committed. Each `-m` is one message paragraph; put the attribution trailers in the last one.

Apply fetches again and stops on any blocker. It runs `gitleaks-preflight` (history and working tree), commits the paths, and pushes `HEAD` to the upstream branch (`-u` on first push). Hooks run and author identity is kept. If a path outside the set is already staged, the commit stops.

Exit codes: `0` done or nothing to do; `1` blocked or failed (see `blockers`); `2` plan has pending work.

On a failed scan, use `gitleaks-preflight` to inspect redacted findings. Allowlist only confirmed false positives. Never print secret values or read credential or env files.

Never force-push, skip hooks, or amend unless Cohen asks. After a failed or timed-out push, check `git ls-remote <remote> <branch>` before you do anything else. Never rerun apply or a deploy automatically.

## 3. Deploy

The helper never deploys. Follow the project's `AGENTS.md`. For Cloudflare, use `deploy-cloudflare` and keep named Worker environments.

If CI deploys the pushed branch, track that run for the pushed SHA until it succeeds. Do not also deploy by hand. A queued run is pending, not shipped. For a manual deploy, run the scan on the final deploy inputs, then deploy once with the project's command.

## 4. Verify and report

Check the live URL with `ego-browser` (Ego Lite). If it cannot connect, say browser QA was skipped and finish the other checks. Confirm `git status` is clean for the shipped paths and the remote SHA matches `HEAD`.

Report: project, commit SHA, push destination, deploy status and URL, checks run with results, and anything blocked or unverified. Say "shipped" only for outcomes you confirmed.
