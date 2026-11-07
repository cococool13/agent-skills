# Inventory and baseline

## Inventory

Walk the scoped tree once. Write `map.md` and `coverage.md` in the run folder.

1. Read the README, deploy and build config, and dependency list.
2. List every entry point you can find: HTTP route, queue consumer, cron, webhook, deep link, URL scheme, app intent, exported symbol, CLI command, background task, push handler. Search the usual tables (`routes`, `@app.route`, webhook paths, URL schemes, background identifiers). The search is scoped to the path or area the user named; outside that path, write a coverage gap.
3. For each entry point, name the actor, the input, the store writes, the outbound calls, and the success result.
4. Mark flows that touch money, authentication, authorization, personal data, or platform entitlements.
5. List implicit state: status columns, paired booleans, step numbers, "isLoading / isError / isEmpty" flags, sync cursors, retry counters.
6. Write `coverage.md`: the globs or paths you inspected, the review slice that owns each inspected path, and explicit gaps (unopened generated code, vendored trees, files outside the scoped area, files you did not open). A file or tree no slice lists is a gap, not "fine." Do not claim every source file in the repository was reviewed.

A scanner hit (unused code, complexity, a linter warning) is a lead, not a finding. Search the scoped tree, including tests, fixtures, generated routes, and string references, before calling code dead.

Do not open secret files to "confirm" contents. Record that a secret-looking path exists (`.env`, `*.pem`, keychain exports) without printing values.

### Recipe: map an entry point

- **Prerequisites:** repo docs, route tables, generated clients if present.
- **Input:** one concrete entry (for example `POST /pairs` or a Device Activity extension).
- **Expected fail:** the map omits a writer, an outbound call, or an actor who can reach it.
- **Expected pass:** actor, input, writes, outbound calls, and success result are named, and money/auth/personal-data flags are marked if they apply.
- **Artifact:** a row in `map.md`.
- **ROI / stop:** worth it for every reachable entry in scope. Stop when a search of the scoped tree adds no new row.

### Recipe: coverage manifest

- **Prerequisites:** the scoped path and the files you actually opened or searched.
- **Input:** inspected globs plus known-unreviewed trees.
- **Expected fail:** the manifest claims completeness, or a tree you skipped is missing from Gaps.
- **Expected pass:** a reader can see what was inspected and what was not.
- **Artifact:** `coverage.md`.
- **ROI / stop:** always worth it. Stop once gaps are named; do not open every remaining file to empty the Gaps list.

## Baseline

1. Run the project's own checks with the same commands the repo documents. Record the command and the pass, fail, and skip counts in `baseline.md`.
2. Note CI jobs that fail in seconds with no runner and no logs. That is often billing or quota, not a code defect.
3. If dependencies are not installed, run the repo's own lockfile install (`npm ci`, `pnpm install --frozen-lockfile`, `swift package resolve`, and so on) when the house rules allow project-local installs; otherwise ask. Never install globally, upgrade a lockfile, or bump a toolchain to make a gate run. If it still cannot run, record the gate as "not run" and name the missing toolchain.
4. Code you cannot compile here is "needs <toolchain>." Do not edit it in implement mode beyond mechanically safe changes. Do not claim an unrun check passed.

Later work must not make the recorded counts worse. If implement mode fixes a failure that was already red at baseline, say so instead of treating the new green as proof you introduced no regressions.

Running the baseline does not edit the repo. It belongs in report-only mode.

### Recipe: record the gate

- **Prerequisites:** documented test/lint/typecheck commands; dependencies installed from the lockfile (step 3).
- **Input:** the exact documented command(s).
- **Expected fail:** the command is missing, the toolchain is absent, or the suite is already red.
- **Expected pass:** command, counts, and duration are copied into `baseline.md`.
- **Artifact:** `baseline.md` plus raw output in the run folder.
- **ROI / stop:** always worth it before you change or judge the tree. Stop after the documented local gate; do not invent a second suite.

## Stop

You can leave this phase when `map.md` names the entry points you found in scope, `coverage.md` lists inspected paths and gaps, and `baseline.md` has real commands or a clear reason a command did not run.
