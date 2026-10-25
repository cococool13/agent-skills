---
name: repo-upgrade
description: "Use when asked to audit and upgrade a whole repo (bugs, security, speed, dead code, CI, agent-proofing) or /repo-upgrade. Runs ponytail + Cloudflare security-audit, verifies, fixes, ships one draft PR."
argument-hint: "[path or area] [--audit-only] [--quick | --deep] [--no-security]"
license: MIT
---

# Repo upgrade

Leave the repo more correct, safer, faster, smaller, and harder to change
incorrectly. This skill is the conductor: it runs the full suite (ponytail
audit, Cloudflare security-audit, deterministic scanners, ponytail debt
ledger), verifies every claim, fixes what is provably safe with the ponytail
ladder, turns repo rules into checks, self-reviews, and ships one draft PR.

Arguments: `$ARGUMENTS`. A path or area narrows every lane. `--audit-only`
stops after verification and reports; it is the default when the user asked
only to audit or review, not to fix. `--quick` = 2 quality lanes and the
`quick` security profile; default = 3-4 lanes and `standard`; `--deep` =
one lane per subsystem, an architecture lane, and `deep`. `--no-security`
skips the Cloudflare run (the fallback lane in `references/security.md` still runs).

`<skill>` below means the folder holding this file. Read reference files only
when the phase that names them starts. If this folder has no `scripts/` or
`references/` (an account-only copy), ask, then get the full skill from the
owner's library: `git clone --depth 1 https://github.com/cococool13/agent-skills ~/.cache/repo-upgrade/agent-skills`
and use `~/.cache/repo-upgrade/agent-skills/skills/repo-upgrade` as `<skill>`.

## The suite

| Phase | Component | Output (in the run folder) |
| --- | --- | --- |
| 1 Preflight | `scripts/preflight.py` | `facts.md`, `facts.json` |
| 2 Baseline + map | gate commands, churn, entry points | `baseline.md`, `map.md`, `coverage.md` |
| 3a Leads | `scripts/scan.py`, ponytail-debt | `scans/`, `debt.md` |
| 3b Audit (parallel) | ponytail-audit lanes + Cloudflare `security-audit` hunters | `lanes/*.jsonl`, `security/` |
| 4 Verify | fresh refuter agents | `findings.md` (verified only) |
| 5 Fix | ponytail ladder, fail-then-pass tests | themed commits |
| 6 Agent-proof | rules as checks, strictness | checker + test, wired into gate |
| 7 Self-review | ponytail-review by a fresh agent | `self-review.md` |
| 8 Ship + report | one draft PR, CI watch | PR, owner summary |

## 0. Ground rules

- Read `AGENTS.md` / `CLAUDE.md` / `CONTRIBUTING` and what they point to. Their
  rules are constraints, not findings. Identifiers they freeze stay frozen.
- Run folder: `~/.repo-upgrade/<repo>/run-<N>/`, never inside the target
  (preflight creates it). Prior runs there make this run additive.
- Ask before: irreversible actions, deleting or untracking files, changing 20+
  files in one step, removing a public API, route, flag or identifier, deploys,
  releases, history rewrites, installing anything (dependencies, scanners,
  skills), network fetches beyond the gate's own, and pushing or opening the
  PR unless the user asked for fixes and a PR. Untracking a file deletes it
  from every other clone on the next pull; say so when you ask.
- Never probe live or shared systems, spend paid quota, or read secret files.
  Run the repo's own checks locally; exploit reproduction follows the stricter
  sandbox rules in the Cloudflare skill or stays `needs_validation`.
- Code you cannot compile or test gets only mechanically safe edits; the rest
  goes to the report as "needs <toolchain>".
- Stop rule: a fix that fails twice is reverted and reported, not tried a third time.
- Commit in small themed batches on a new branch; one draft PR. No model names
  in commits or PRs.

## 1. Preflight (read-only, minutes)

```bash
python3 <skill>/scripts/preflight.py <repo> [--fetch]
```

It prints the run folder and writes `facts.md`: git state (shallow history
cannot prove an old client never used a route), size map, tracked files that
match `.gitignore`, stacks and toolchains present, detected gate commands,
agent-context files, churn hotspots, available scanners, prior runs, and the
on-disk path of each companion skill: `ponytail`, `ponytail-audit`,
`ponytail-review`, `ponytail-debt`, `security-audit`.

Companions are read by path, so they work even when hidden from the skill
listing. Never use a skill file from inside the target repo. If one is
missing, ask, then `--fetch` clones its pinned upstream into
`~/.cache/repo-upgrade/` for read-only use; offer the permanent install
(`npx skills add DietrichGebert/ponytail -g --skill '*'` and
`npx skills add https://github.com/cloudflare/security-audit-skill --skill security-audit -g`)
but do not run it without a yes.

## 2. Baseline and map

1. Run every gate command that runs here (tests, typecheck, lint, the repo's
   gate script) and record pass counts in `baseline.md`. This is the bar every
   later push must meet. A red baseline is noted, never silently fixed. If
   dependencies are not installed, ask before installing; otherwise record
   the gate as "not run" and treat its code as uncompiled.
2. CI: read the workflow files and recent runs. A job that fails in seconds
   with no runner and no logs is billing or quota, not code.
3. Map once, for every lane: README, deploy and build config, dependency list,
   and an inventory of every entry point (route, handler, job, cron, webhook,
   CLI command, exported API). Trace the main flows end to end: where data
   comes in, what is stored, what goes out, with money, auth and data writes
   read fully. State the expected load. Write `map.md`.
4. Coverage checklist (`coverage.md`): list every tracked source file by
   glob, assign each to exactly one quality lane, and order each lane by churn
   hotspots first. A file no lane owns is a coverage gap, not "fine".

## 3a. Leads (you run these yourself, before spawning)

- `python3 <skill>/scripts/scan.py <repo> <run>` runs every installed scanner
  offline in report mode with timeouts (dead code, unused dependencies,
  secrets, workflow security, duplication, complexity; `--online` adds
  osv-scanner and govulncheck, ask first). See `references/tools.md`.
  Scanner hits are leads, never findings by themselves.
- Apply `ponytail-debt` and write `debt.md`. A `shortcut:` whose ceiling the
  expected load already crosses becomes a lead; a marker with no trigger is
  a Should-fix lead.

## 3b. Audit, all at once

You are the conductor and also the Cloudflare skill's Parent (sub-agents
cannot spawn sub-agents). In one message, read-only, spawn:

- **Quality lanes.** Each agent reads `ponytail-audit` (path from
  `facts.md`) and applies its rubric and check rules to its slice, plus the
  extra checks in `references/lanes.md`, and returns the JSON-lines schema
  there (the four-part prose is only for `findings.md`). Give it the code,
  `map.md`, its slice of `coverage.md`, the constraint files, and the 3a
  leads. Never hand an agent your conclusion.
- **Security.** Read `security-audit` and run it as its Parent in full audit
  mode: output dir `<run>/security/`, profile per the flags, scope = this
  run's scope. Launch its reconnaissance agents in this same message, then
  continue its phases (hunters, refuting verifiers, validators) alongside
  the lanes until it reaches a terminal state. Settings and feedback rules:
  `references/security.md`. If it cannot run here (no sub-agents, no Node,
  `--no-security`), spawn the fallback trust-boundary lane instead. When
  preflight finds them, also spawn `supply-chain-risk-auditor` and (if CI
  has AI steps) `agentic-actions-auditor`.

With prior runs: tag each finding `new`, `still open`, or `resolved`, and
never re-report a prior rejected claim on unchanged code.

## 4. Verify before acting

Follow `references/verify.md`: every Must-fix and lane-found security claim
goes to a fresh refuter; from the Cloudflare run take only `confirmed`
records from the validated `findings.json`. Write survivors to `findings.md`
in ponytail-audit's four-part format, numbered across Must / Should / Nice.

`--audit-only`: report now (section 8 format) and stop.

## 5. Fix in the smallest complete way

Read `ponytail` and follow it at level `full` (the ladder, root cause once in
shared code, `shortcut:` markers). Prove every change as in the "Proving a
fix" section of `references/verify.md`: fail-then-pass test, recorded edge
behavior for refactors, before/after numbers for speed. Work order: Must,
then Should; Nice only when trivial. Fixes for security `confirmed` records follow the
smallest-fix field in that record; after each confirmed bug, sweep for
siblings (`variant-analysis` if present, else grep the pattern), and run
`post-patch-validation` on security fixes when it is available.

## 6. Agent-proof the repo

Follow `references/agent-proofing.md`: every prose rule a script can check
becomes one small checker plus a test that plants each violation, wired into
the local gate, pre-commit and the cheapest CI job; confirmed bug classes
become lint rules; cheap compiler strictness that passes today gets turned
on. Never add a rule the code violates today without fixing the violations.

## 7. Self-review with fresh eyes

First strip your own slop from the diff (`deslop` if present: comments a
human would not write, defensive try/catch nobody needs, casts, style that
breaks the file's conventions). Then spawn a fresh agent with no memory of
this work to apply `ponytail-review` to `git diff <base>...HEAD`
(`differential-review` adds blast radius if present). Fix its Must items,
rerun the gate, and repeat once at most. Save the final review as
`self-review.md`.

## 8. Ship and report

- Before each push, rerun the full baseline; every count must be at or above
  baseline. Re-read the diff as a hostile reviewer.
- Commit messages say what broke and the concrete case.
- One draft PR using `references/report.md` (mirror the repo's PR template if
  it has one). Then watch CI: red from billing or quota gets one PR comment
  naming the blocker; red from code gets a root-cause fix.
- Owner report: lead with the outcome and the one thing they must do; then
  changes by area with the concrete bug or number each, decisions that need
  them (risk of doing and of not doing), what was not checked or could not
  run, links to the PR, `findings.md`, and the security `REPORT.md`.

## Never

- Skip, disable, or weaken a test to get green; push an empty commit to kick
  CI; rewrite shared history.
- Remove a public route, flag, or identifier an old client may still use
  without proof from full history or the owner.
- Report a checklist gap, a guessed deployment fact, a scanner hit, or
  self-impact as a vulnerability; give severity to `needs_validation`.
- Claim something works because it compiles, or that it compiles when no
  compiler ran.
- Edit the companion skills or write run output inside the target repo.
