---
name: ship
description: "Use when Cohen runs /ship or asks to commit, push, and deploy the current repo only."
disable-model-invocation: true
---

# Ship

`/ship` gives permission to commit, push, and deploy the active project. Obey the project `AGENTS.md` and any narrower request. Do not send an app to the App Store. Ask Cohen for each step the project marks as owner-only. A request to edit this skill is not permission to ship.

Work in the current Git repository only. If the current directory is not a repository, stop and say which project is missing.

## 1. Plan

Read the project `AGENTS.md` for build, test, and deploy steps. Then run:

```bash
python3 ~/.agents/skills/ship/scripts/ship.py
```

Plan mode fetches the remote and prints JSON. It changes nothing. Read:

- `buckets`: `secret`, `noise`, and `archive` are excluded; never commit them. `commit` holds the other changed files. Read the diff and commit only the files for this task.
- `unpushed` (max 20) and `ahead`: every commit a push will send. If one is not part of this task, stop. A push with no upstream sends the full branch.
- `blockers` (files over 100 MB, and others): remove each before Apply. `warnings` (over 50 MB): put in the report.
- `cleanup`: other worktrees. Apply removes only clean, unlocked, fully merged worktrees, and moves leftover directories to Trash. Never use `rm`.

If the branch is behind, add only this task's changes. Do not touch other branches or stashes. Run the build, tests, and checks on the final code and fix each failure.

## 2. Apply

```bash
python3 ~/.agents/skills/ship/scripts/ship.py --apply -m "<type>: <imperative summary>" -m "<trailers>" [path ...]
```

Pass exact paths when `commit` holds files outside this task; with no paths, the full `commit` bucket is committed. Each `-m` is one paragraph; trailers go last.

Apply re-fetches, stops on blockers, runs `gitleaks-preflight`, commits, pushes `HEAD` (with `-u` on the first push), and then removes old worktrees. Exit codes: `0` done or nothing to do; `1` blocked or failed (read `blockers`); `2` pending work.

If the scan fails, use `gitleaks-preflight` and read only the redacted result. Allow a finding only after you confirm a false positive. Never print a secret or read a credential or environment file.

Do not force-push, skip hooks, or amend unless Cohen asks. If a push fails or times out, run `git ls-remote <remote> <branch>` before anything else. Never re-run Apply or a deploy automatically.

## 3. Deploy

`ship.py` does not deploy. Use the project's release scripts and the `deploy-cloudflare` skill. Keep each named Worker environment.

If CI deploys the pushed branch, follow that run for the pushed SHA until it succeeds. Do not also deploy by hand. A queued run is not shipped.

A manual deploy uploads the working tree or its build, not the commit. Commit first, then build. Stop if a dirty or untracked file would be uploaded (check `public/`, asset folders, `dist`). Scan the final deploy inputs, then run the deploy command once.

## 4. Check and report

Open the live URL in `ego-browser`; use Claude in Chrome when the check needs Cohen's logged-in session. If no browser connects, say the browser check did not run and finish the other checks. Confirm `git status` is clean for the shipped paths and the remote SHA equals `HEAD`.

Report the project, commit SHA, push destination, deploy status, URL, each check and result, each blocker, each removed worktree or Trash move, and each item not verified. Say "shipped" only for a confirmed result.
