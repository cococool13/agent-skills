# Quality lanes

Each lane applies `ponytail-audit` (rubric, "check before you report" rules,
four-part finding format) to its slice of `coverage.md`. This file adds only
what ponytail-audit does not cover and the brief and output contract.

## Splitting

3 or 4 lanes by stack area, e.g. backend/API, app/client, data and jobs,
tooling/CI/docs. A lane gets whole flows, not random files: the route, its
handler, its store calls and its tests belong together. Give the biggest or
riskiest area (money, auth, data writes, highest churn) its own lane.

## Extra checks (on top of ponytail-audit's six groups)

Sharpen ponytail-audit's groups with: DST and Unicode surrogate edges,
state checked before an `await` that can change it, and sequential awaits
inside a lock or request where the I/O is independent.

7. **Repo hygiene:** tracked build output, duplicate binaries (prove with
   sha256), tracked files that match `.gitignore` (from `facts.md`), broken
   relative doc links, docs that contradict code, lockfile drift.
8. **CI cost and speed:** path filters on expensive runners (macOS, GPU),
   `concurrency` with cancel-in-progress, job timeouts, caches keyed on
   lockfiles, actions pinned to full SHAs, `permissions: contents: read` by
   default, cheap checks on the cheapest runner, jobs that never fail
   (`|| true`, `continue-on-error`), dependency-bot PRs that trigger
   irrelevant jobs.
9. **Agent-context drift:** `AGENTS.md` / `CLAUDE.md` / rules files that
   repeat each other, name commands that no longer exist, or contradict the
   code. One source of truth; others point to it.
10. **Rules that could be checks:** every prose rule in the constraint files a
   script could enforce (forbidden names, literal colors outside the design
   system, frozen identifiers, banned imports, required calls). List them for
   phase 6; they are not findings unless the code violates them today.

## Churn first

Work through the slice in `coverage.md` order (churn hotspots first). High
churn plus high complexity is where bugs live and where a fix pays most.
Say which files you did not read.

## Brief template

```
You are a read-only audit lane for <repo> at <sha>. Do not edit anything.
Scope: <paths from coverage.md, in order>. Constraints: read <AGENTS.md ...>.
Shared context: <run>/map.md (entry points, flows, expected load), <run>/facts.md.
Leads (unverified): <run>/scans/summary.md, <run>/debt.md.
Toolchains here: <from facts.md>. Code you cannot compile: say so per finding.
Method: read <ponytail-audit path> and apply its rubric and check rules,
plus checks 7-10 in <skill>/references/lanes.md.
Return at most 20 findings as the JSON lines below, ranked, then a
"Not checked:" list. No finding without a concrete failing case.
```

## Finding schema (one JSON object per line)

```json
{"id":"L1-3","lane":"backend","group":"must|should|nice","kind":"bug|risk|scale|test|speed|lean|hygiene|ci|context",
 "title":"Orders land on the wrong day","where":"billing/close_day.py:40-52",
 "case":"order at 00:30 Berlin is billed the previous day",
 "fix":"compute the day in the shop time zone (one line)",
 "skip_cost":"wrong dates, manual accounting fixes",
 "confidence":"high|medium|low","safe_without_compiler":true,"prior":"new|still open|resolved"}
```

The parent merges lanes, dedupes by `where` + root cause, and renumbers.
