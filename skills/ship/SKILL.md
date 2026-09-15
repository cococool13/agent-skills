---
name: ship
description: "Commit, push, and deploy the current project when the user invokes /ship."
disable-model-invocation: true
---

# Ship

An invocation of `/ship` authorizes commit, push, and deployment for the active project, subject to project instructions and any narrower request. A request to edit or audit this skill does not authorize shipping.

Work in the current Git checkout only. Read its applicable `AGENTS.md` and `CLAUDE.md` before changes. If cwd is not a repository, stop and identify the missing project.

## Prepare

Inspect the branch, status and relevant diff. Select only task-related changes; the helper's file buckets are exclusions, not proof of relevance. If unrelated files would enter its commit set, commit the intended paths explicitly and use the helper only for inspection; finish the authorized push directly with an explicit remote and branch after the checks below.

```bash
python3 ~/.agents/skills/ship/scripts/ship.py --plan-only --json
```

The plan uses local refs and does not fetch, scan, copy docs, clean worktrees or integrate leftover branches. See [reference.md](reference.md) for the command contract and exclusions.

If the project requires integration into its release branch, integrate only the task's changes, respecting active worktrees and project rules. Run the project's required build, tests and checks against the final code before pushing. Fix failures locally. If apply fetches newer upstream commits, it stops so you can integrate and repeat affected validation first.

## Apply

Once the commit set and final code are verified:

```bash
python3 ~/.agents/skills/ship/scripts/ship.py --apply --json
```

Apply fetches, requires a passing gitleaks preflight, commits the selected bucket and pushes the current branch to its explicit upstream destination. It stops on failure. It preserves commit identity and performs no branch/stash deletion, worktree cleanup, doc copying or automatic leftover merges.

For a direct push outside the helper, run `gitleaks-preflight` first. On a failed scan, use that skill to inspect redacted findings; allowlist only confirmed false positives. Never print secret values or read credential/environment files into agent context. Do not weaken a scan just to pass it.

Never force-push, bypass hooks or amend unless the user explicitly asks. Inspect a failed operation before continuing. Do not automatically retry a push or deploy, including by rerunning the full helper after an uncertain result.

## Deploy and verify

The helper does not deploy. Its deploy hint is not authoritative: read the project's deployment instructions even when no hint appears.

For Cloudflare, use `deploy-cloudflare`; honor a different provider only when project instructions specify it. Preserve named Worker environments. Confirm whether CI deploys the exact pushed branch and revision; track that run to success instead of also deploying manually. A queued run is pending, not shipped. For manual deployment, scan the final deployment inputs, then deploy once using the project's command.

Check the live result with `ego-browser` / Ego Lite. If it cannot connect, report that browser QA was skipped and finish the remaining verification.

Recheck local Git status and upstream revision without reapplying. Confirm the pushed commit and deployment result independently; a persistent deploy hint is not evidence that another deploy is needed.

Report the project, commit, push destination, deployment status and URL, checks and results, plus anything blocked or unverified. Use “shipped” only for the outcomes actually confirmed.
