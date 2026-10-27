# Autonomous release profiles

The agent derives this profile from the repository's instructions and reviewed
scripts. This is an agent review, not a request for Cohen to approve each field.
Prefer checked-in `ship.toml` for stable project facts. For a one-run adaptation,
use `<git-common-dir>/ship/profile.toml`; the helper finds it automatically when
the root profile is absent. `--profile` accepts one of those named TOML files in
the repository or its private ship state. Python 3.11 or newer is required.
Never put credentials, environment values, arbitrary instructions, or auth files
in a profile. The helper never loads environment/credential files as profiles.

## Common schema

```toml
version = 1
main = "main"
remote = "origin"
integration = "direct" # "pr" for protected main / required PR workflows
artifacts = ["dist"]

# Optional frozen dependency install, only in the isolated validation checkout.
[[prepare]]
argv = ["npm", "ci"]
timeout = 600

[[checks]]
argv = ["npm", "run", "verify"]
cwd = "."
timeout = 1800

[deploy]
mode = "ci"
workflows = ["deploy.yml"]
branch = "main"
event = "push"
timeout = 1800

[[smoke]]
url = "https://example.com/health"
contains = "{sha}"
status = 200
```

Use the actual package manager and native scripts. `checks` must be nonempty;
include the project-required build, test, lint, and release gates, not a dummy
command. Each check/prepare row accepts only `argv`, `cwd`, and `timeout`.
Arguments are arrays, run without a shell; paths are relative to the isolated
checkout and cannot escape it. Commands are sequential and noninteractive.
Default working directory is `.`; timeout is 900 seconds, maximum 86400.
Do not run deploys, publishing, Git commits, or App Review in prepare/checks.
Inspect scripts so innocently named checks do not hide those actions.

Root fields are `version`, `main`, `remote`, `integration`, `artifacts`,
`prepare`, `checks`, `deploy`, `publish`, and `smoke`. Unknown fields fail closed.
Artifacts must exist after checks; they are scanned with redacted gitleaks and
hashed without opening protected filenames. Symlinks are rejected. Outputs
should be ignored by Git so validation never edits committed inputs.

`integration = "pr"` pushes the validated candidate to a recorded release
branch, creates one PR, requests normal merge/auto-merge with an exact head-SHA
match, and monitors it without bypassing rules. After merge, the actual main
commit is validated again before the remaining release stages. It does not
delete the PR branch. Required owner reviews can still block; ordinary checks
are watched automatically. Set an adequate deployment timeout for the PR/CI.

Read the project's required preview QA and run it before production publication.
CI jobs that publish on main must enforce their own required validation gates;
the helper cannot undo a main-triggered deploy after that push/PR merge.

## Deployment modes

`none`: use `[deploy] mode = "none"` only when the project has no deployment.
Publishing steps can still distribute native artifacts or GitHub releases.
Do not declare none merely because discovering the release script takes work.

`ci`: list every required workflow by its exact filename or name. The helper
queries by full commit SHA, workflow, branch, and event, stores run IDs and
attempts, and waits. Failure/cancelled/skipped is not success. Missing runs time
out; they never trigger a duplicate manual deployment. Owner-action states stop
with the recorded run so the agent can name the actual requirement.

`command`: existing Pages/native/custom deploy scripts, with independent identity:

```toml
[deploy]
mode = "command"
argv = ["./scripts/deploy.sh", "{sha}"]
verify = ["python3", "scripts/release-status.py", "{sha}"]
cwd = "."
timeout = 1800
```

The verify command must be read-only and print one JSON object with
`{"sha":"<full-sha>","deployed":true}` for that exact release. Suppress
diagnostics and never print credentials. This enables safe reconciliation of
an interrupted command. If verification is unavailable, use the owning tools
to implement a small status adapter rather than running an unverified deploy.

`cloudflare`: promote the exact uploaded Worker version:

```toml
[deploy]
mode = "cloudflare"
wrangler = ["npx", "--no-install", "wrangler"]
name = "the-project-worker"
environment = "production"
account = "the-documented-account-id"
config = "wrangler.release.jsonc"
cwd = "."
timeout = 1800
probe = ["python3", "scripts/probe-worker-version.py", "{version}", "{sha}"]
identity_url = "https://example.com/__release"
```

Use the project's pinned Wrangler. Explicit account/name/environment/config
prevent a bare deploy from reaching another Worker. The account ID is a
nonsecret identifier. Preserve the documented environment, including an empty
environment only through a project command adapter if that is the actual setup.
The release config must point at already built code/assets; upload uses
`--no-bundle`. Confirm project configuration does not rebuild different inputs.

The helper records the current deployment, uploads one uniquely tagged version,
finds its ID by that tag, verifies artifact digests did not change, runs `probe`,
promotes that version to 100%, confirms the active version, and checks live
identity. The read-only probe prints
`{"sha":"<full-sha>","version":"<version-id>","verified":true}` only after
testing the uploaded version. Its implementation depends on the project's
available Version URL / isolated preview / version-override workflow. It must
not silently test whatever version happens to be live.

The live identity URL returns
`{"sha":"<full-sha>","version":"<version-id>"}`. Use Cloudflare's version
metadata binding for the version ID; supply the commit identity through the
project build. Health/identity checks are read-only. A propagation delay can be
handled by resuming read-only verification; do not repeat promotion.

Version URLs use the uploaded version's production resources. Use isolated
Previews/environments for signup/payment/data-write tests. Durable Objects,
migrations, first-ever deployments, and Pages have different release mechanics;
use their documented command/CI adapter instead of forcing this Worker path.
The previous deployment is recorded for recovery, but storage/migrations are
not rolled back automatically. No global canary or automatic rollback is added.

## Publishing and live checks

```toml
[[publish]]
argv = ["./scripts/publish-built-release.sh", "{sha}"]
cwd = "."
timeout = 3600
verify = ["python3", "scripts/published-status.py", "{sha}"]

[[smoke]]
url = "https://example.com/download"
contains = "Download"
status = 200
```

Publish commands run after successful deployment/smoke checks from the validated
checkout, using its artifacts. Reuse existing project release scripts and
licensing/distribution rules. The optional read-only publish verify adapter
returns `{"sha":"<full-sha>","published":true}`. Provide it whenever the
provider permits, so uncertain publication can be reconciled without replay.
Without a verify adapter, a confirmed exit is recorded, but an interrupted
publish is a genuine blocker until its external outcome can be established.
Never submit for App Review; direct `--submit`/`review-send` arguments are rejected.

Only `{sha}`, `{run_id}`, and `{version}` are substituted in release arguments;
these are exact values recorded in the journal, not shell expansion. A smoke
row accepts `url`, optional `contains`, and `status`. HTTPS is required except
local fixtures. An expected marker can contain `{sha}` or `{version}`.
Smoke checks complement, rather than replace, the actual browser/native flow.

## Recovery, scope, and evidence

`--all` plans without modifying the checkout. `--all --apply` releases. `--status`
reads the journal without taking the release lock. `--resume` locks, reconciles,
and continues an existing release. Normal invocation should use those modes.
The older task-scoped flags remain available for contained repair operations.

The OS lock is shared via Git's common directory, so linked worktrees cannot
start two repo-wide ships. It is advisory: editors and unrelated Git commands
do not honor it. Source/HEAD/destination checks still apply. For separate
machines, add a production deployment concurrency group in the project's CI.
Do not cancel an active production deployment by default.

The journal contains source tips, check verdicts, commit/tree IDs, artifact
digests, release operation intent/outcome, PR/CI/version/deployment identities,
and live-check evidence. It does not contain raw command/scanner logs. Writes
are atomic. Each external intent is persisted before the operation; a resumed
process never repeats an uncertain push/upload/deploy/publish blindly.
Each run is also retained under `ship/runs/<run-id>.json`. A new release does
not erase the previous run's evidence. Unchanged completed releases are checked
read-only without repeating publication; `--all --apply --new-release` requests
a deliberate new release only after the previous run is complete.

Before external operations, fix local checks/conflicts/profile commands and
resume. After an external operation begins, profile/destination/validated input
changes block: reconcile the existing release rather than producing different
artifacts under the same run ID. Do not manually change an uncertain operation
to done without independent provider evidence.

All captured source tips are preserved in main. Registered source worktree
branches are fast-forwarded to the unified commit when safe. Excluded local
files remain and are reported. Retained branch/worktree deletion is not part
of shipping. Internal validation worktrees are retained as release evidence
and excluded from future collection; review them separately if storage matters.

Primary references: [Git worktrees](https://git-scm.com/docs/git-worktree),
[Git push](https://git-scm.com/docs/git-push),
[GitHub run queries](https://cli.github.com/manual/gh_run_list),
[Cloudflare version commands](https://developers.cloudflare.com/workers/wrangler/commands/workers/),
[Cloudflare preview comparison](https://developers.cloudflare.com/workers/previews/compare-workflows/),
[Cloudflare version metadata](https://developers.cloudflare.com/workers/runtime-apis/bindings/version-metadata/).
