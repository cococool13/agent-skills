---
name: ship
description: "Use when Cohen runs /ship or asks to commit, push, and deploy the current repo only."
disable-model-invocation: true
---

# Ship

`/ship` authorizes commit, push, deploy, and live checks for the active project. Run the full flow without check-ins. Stop only for a blocker you cannot fix or a step the project `AGENTS.md` marks owner-only. Project release scripts may upload to TestFlight and notarize; never submit for App Review without Cohen's explicit yes. A request to edit this skill is not permission to ship.

Work in the current Git repository only. If there is none, stop and name the missing project.

## 1. Plan and check

Read the release section of the project `AGENTS.md`, then run:

```bash
python3 ~/.agents/skills/ship/scripts/ship.py
```

Plan mode fetches, changes nothing, and prints one JSON line. Exit `0` nothing to ship, `1` blocked, `2` work pending.

- `repo.buckets.commit`: changed files. Commit only this task's files; name them as paths when others are present. `secret`, `noise`, and `archive` never commit.
- `repo.unpushed` / `repo.ahead`: every commit the push sends. Stop if one is not part of this task.
- `blockers`: fix each and plan again. `warnings`: carry into the report.
- `pending`: what Apply will do (`commit`, `integrate`, `push`, `cleanup`).
- `deploy`: CI workflows, deploy scripts, and Wrangler configs found in the repo.
- Session or feature branch (`repo.branch` is not `repo.default_branch`): if the project deploys from the default branch and does not require PRs, add `--to <default_branch>` to Apply. Otherwise push the branch.

Run the project's build, tests, and lint/format on the final code and fix each failure.

## 2. Apply

```bash
python3 ~/.agents/skills/ship/scripts/ship.py --apply -m "<type>: <imperative summary>" -m "<trailers>" [--to <branch>] [path ...]
```

Each `-m` is one paragraph; trailers go last. With no paths, the whole `commit` bucket is committed. Apply re-fetches, then: stages, scans the staged diff and unpushed commits with gitleaks (verdict only), commits, rebases onto the remote branch if behind, pushes `HEAD` (never forced), confirms the remote SHA (`verified`), and removes old worktrees (clean, merged, untouched for 72 hours; leftover folders go to Trash).

- `revalidate` (exit `2`): upstream commits were rebased in. Re-run the checks, then run Apply again with no `-m` and no paths (plus the same `--to`). Without `-m` and paths, Apply never commits; it only pushes.
- Rebase conflict: Apply aborts the rebase and the commit stays local. Resolve it, re-run checks, apply again.
- Scan finding: nothing is committed and the index is restored. Use `gitleaks-preflight` and read only redacted output. Allow a finding only after you confirm a false positive.
- Push failed or timed out: run `git ls-remote <remote> <branch>` first. Never re-run Apply or a deploy automatically.
- Do not force-push, skip hooks, or amend unless Cohen asks. Never print a secret or read a credential or environment file.

## 3. Deploy

- CI deploys the pushed branch (see `deploy.ci`): do not also deploy by hand. Find the run with `gh run list --commit <sha> --json databaseId,status,workflowName`, then run `gh run watch <id> --exit-status` in the background. A queued run is not shipped.
- Manual deploy: use the project's release script (`deploy.scripts`) and the `deploy-cloudflare` skill; keep each named Worker environment. A manual deploy uploads the working tree, not the commit: stop if `left` lists files inside the deploy inputs. Build, scan the output with `gitleaks dir <output> --redact --no-banner`, then deploy once.
- No deploy defined: say so. The verified push is the ship.

## 4. Verify and report

Open the live URL and confirm the change itself, not only an HTTP 200. Use the built-in browser pane in Claude desktop, `ego-browser` in other clients, and Claude in Chrome when the check needs Cohen's logged-in session. If no browser connects, say the browser check did not run and finish the rest.

Report the project, commit SHA, push destination and `verified`, deploy status and URL, each check and its result, warnings, removed worktrees and Trash moves, and each item not verified. Say "shipped" only when the push is verified and any deploy is confirmed live.
