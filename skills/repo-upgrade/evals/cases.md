# Evals for repo-upgrade

Grow this one case at a time: every time a run misses something a human
later catches, add a case. Run each case with and without the skill to
measure the lift; a case the bare agent also passes tests nothing.

Each case is a small fixture repo (or a pinned commit of a real one) with
planted problems and what the report must and must not contain.

## Case 1: wrong-day billing (bug lane)
Fixture: a job computing "today" with the server clock in UTC for a shop in
Europe/Berlin. Must find: the time-zone bug with the 00:30 case. Must fix:
one line, plus a test that fails before and passes after.

## Case 2: dead export that looks dead but is not (verify)
Fixture: an exported function referenced only by string in a route table.
Must not delete it. Must show the grep evidence in the verify step.

## Case 3: IDOR (security)
Fixture: `GET /invoices/:id` checks login but not ownership. Must report it
as confirmed with all six trust-boundary parts, severity high, smallest fix at
the handler, regression test with a second dummy user.

## Case 4: unpinned action with write token (CI lane)
Fixture: workflow using `actions/checkout@v4` and `permissions: write-all`
on `pull_request_target`. Must flag both; must pin to a full SHA and set
`contents: read`.

## Case 5: shortcut over its ceiling (debt ledger)
Fixture: `# shortcut: in-memory cache, fine under 1 process, move to Redis when scaled`
in a repo whose deploy config runs 4 workers. Must report it as a finding;
the same marker in a single-process CLI must not be reported.

## Case 6: refuted claim stays out
Fixture: a "SQL injection" a scanner flags where the value is an enum
validated at the boundary. Must be refuted and absent from `findings.md`.

Scoring: must-find hit rate, must-not violations (false deletions, invented
findings), and whether every fix has a fail-then-pass test.
