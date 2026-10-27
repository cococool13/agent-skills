---
name: ship
description: "Use when Cohen runs /ship or asks to consolidate, commit, merge, push, deploy, and publish the current repository autonomously."
disable-model-invocation: true
user-invocable: true
argument-hint: "[note]"
metadata:
  short-description: "Unify this repo on main and release autonomously"
---

# Ship

`/ship` and `$ship` authorize the entire current repository release: collect all
publishable work, commit it, merge branches and registered worktrees into main,
validate the combined result, push, deploy, publish, and verify. Existing work
in this repository is included even when another task created it. Run to
completion without routine permission questions. Editing this skill alone is
not a release invocation.

Stay in the active Git repository and its registered worktrees. Do not sweep
other projects. Preserve history: no forced pushes, history rewrites, discarded
edits, branch deletion, or worktree deletion. Secrets, ignored local files,
archives and build noise stay outside commits; report leftovers honestly.
App Review submission and credential changes still require explicit separate
authorization. Project owner-only steps remain owner-only.

## Release prose

Keep every commit message, PR title/body/comment/reply, changelog, release note,
upload description, and shipping summary short, plain, and factual. State what
changed and why it matters. Add only relevant checks, a real limitation, or a
required action. One sentence or a few short bullets usually suffice; follow
required project templates without filling optional sections with boilerplate.

No praise, hype, emoji, filler, repeated summaries, process narration, long file
lists, model names, generated-by notices, or AI signatures. Keep SHAs, run IDs,
and detailed logs in the journal unless a reviewer needs them. Do not post a
comment just to announce progress; combine related replies and skip duplicates.
Do not invent claims or remove evidence needed to review the change.

Do not add AI as an author or co-author. Remove AI Co-Authored-By trailers from
new messages, including inherited templates and tool defaults. Preserve real
human credit and required legal notices. The helper filters supplied AI
trailers and blocks a new commit if a hook adds one back. Fix the injecting
source; never skip hooks or rewrite existing history to clean old attribution.

## Discover and decide autonomously

Read the closest project `AGENTS.md` and its release/check scripts. Then run:

```bash
python3 ~/.agents/skills/ship/scripts/ship.py --all
```

This returns the branch/worktree inventory, check candidates and deployment
hints. It does not commit, merge, push, deploy, or publish. Use `--status` to
read a prior release journal. Never call the task-scoped Apply flow for a
normal `/ship`; repo-wide mode includes all local branches, configured-remote
tracking branches, and dirty registered worktrees. Detached dirty work gets a
recovery branch. Internal validation worktrees are excluded from collection.

Resolve the release plan yourself from project evidence. Do not ask Cohen to
select commands, approve a profile, approve individual merges, or confirm the
already-authorized push/deploy/publish. If a profile is absent, create the
smallest reviewed `ship.toml` in this repo or `profile.toml` inside its Git
`ship/` state directory. Read [references/profile.md](references/profile.md)
for its schema and provider requirements. Native apps and monorepos use their
existing scripts and working directories. Never guess a Cloudflare account,
Worker environment, release artifact, or destination.

Inspect every included branch tip and any source-specific release instructions.
Resolve ordinary merge conflicts using the combined intent and tests. No
arbitrary ours/theirs resolution. If another process changes a source, collect
and validate the new work; do not overwrite it or kill the process.

For a protected main branch or a required PR workflow, autonomously use the
project's normal PR route and wait for its checks/merge. Do not disable branch
protections or use an admin bypass. When an external operation has started,
reconcile its recorded SHA/provider identity before any new operation. A
rejection is a technical problem to resolve, not a reason to ask for repeated
release authorization. Stop only for a genuine unresolved conflict, missing
access, owner-only requirement, or an outcome that cannot be established.

## Run the release

```bash
python3 ~/.agents/skills/ship/scripts/ship.py --all --apply
```

Supply `-m "<type>: <short change summary>"` from the actual changes, using
Cohen's note when provided. The helper uses it for snapshots and the PR title.
The helper:

1. Locks this repository across linked worktrees and journals the run.
2. Fetches its remote; snapshots publishable dirty work through normal commit
   hooks and secret scans. Existing partially staged exclusions block safely.
3. Merges the captured branch tips into main, preserving history. A conflict
   aborts that merge and records the source; resolve locally and resume.
4. Runs the required prepare/build/check commands against the final commit in
   an isolated detached worktree. Checks that alter committed inputs block.
5. Scans and hashes artifacts, scans outgoing commits, and pushes the exact
   validated SHA without force. It checks source drift before publication.
6. Tracks exact-SHA CI, promotes a verified Cloudflare version, or runs the
   project's declared release commands. It records intent before every external
   mutation and never blindly repeats an uncertain operation.
7. Runs declared smoke checks and publishing steps, fast-forwards the source
   worktree branches to the unified main commit, and verifies captured tips
   remain reachable. Branches, worktrees, and validation evidence are retained.

If a shared guard requires its existing one-use receipt, issue it with
`~/.agents/hooks/approve-once.py --cwd <absolute-cwd> --command <exact-command>`
immediately before the authorized command, then execute that command separately
in the same directory. Reuse `/ship` authorization; do not ask again. A receipt
cannot override a hard denial or authorize App Review, secret reads, forced
pushes, hook skipping, or unrelated projects. Never weaken shared guards to
make shipping work.

## Recover and finish

```bash
python3 ~/.agents/skills/ship/scripts/ship.py --status
python3 ~/.agents/skills/ship/scripts/ship.py --resume
```

The journal is `<git-common-dir>/ship/latest.json`. Local failures can be fixed
and resumed, including profile/check fixes before external operations begin.
After a push/upload/deploy/publish starts, preserve the validated SHA and
artifacts. Resume reconciles remote/provider state; unknown outcomes block
rather than repeat. Polling status and health endpoints read-only is safe.
Never auto-retry the same state-changing external action.

An unchanged, completed release is verified read-only and not published again.
Use `--all --apply --new-release` only for a deliberate corrective/repeated
release after establishing the prior outcome; it never overrides an unfinished
or uncertain run. Do not create fake source changes to force a redeploy.

If `followup_required` is true, the captured release completed but another
process added work during publication. Start a fresh `--all` release to collect
that work; do not replay the completed run. Continue until the repository is
stable, or report the active source that prevents a stable completion.

Resolve local problems and continue independently. For a terminal blocker,
report its exact cause, preserved work, and next required action. Do not ask
“want me to continue?” or turn a technical failure into another approval flow.

For web launches and signup/checkout/pricing changes, run
`launch-qa-five-personas` on an isolated preview before production promotion;
fix blockers until PASS. Cloudflare Version URLs use production resources and
are not isolated write-test environments. Respect the project's CI deployment
path; never launch a second manual deploy alongside it. Follow
`deploy-cloudflare` for account, environment, output scan, and provider details.
Native release scripts may notarize or upload to TestFlight; never submit to
App Review without Cohen's explicit yes.

After the helper, open the live site/app and exercise the changed behavior.
A successful CI run or HTTP 200 alone does not prove the flow works. Complete
any documented native release or browser checks that require the owning tools.
If a capability is unavailable, name that gap and finish independent work.

Report main's full SHA, remote verification, included branches/worktrees,
checks, deployment/publish identities and URLs, live verification, and excluded
local leftovers. Say “shipped” only when all required release stages are verified.
Do not call the working tree completely clean if protected or excluded files
remain. This skill does not delete retained branches or worktree folders.
