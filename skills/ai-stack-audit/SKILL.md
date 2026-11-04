---
name: ai-stack-audit
description: "Use when Cohen asks to audit or improve AI agent instructions, skills, hooks, MCP setup, permissions, or cross-client configuration."
---

# AI stack audit

Audit before editing. An audit-only request stays read-only. A request to improve
or fix authorizes the scoped local repairs after a concrete findings report,
as defined in the shared AGENTS.md. Reuse that authorization. Account changes,
publication, deletion, and spending keep their existing approval boundaries.

## Scope and output

Use `~/Projects/_review/ai-stack-audit-YYYY-MM-DD/` in America/New_York.
Do not overwrite an existing run's artifacts; use a new suffix if needed.
Keep a baseline, workstream findings, verification, REPORT.md, PLAN.md and the
exact changed-file/rollback record. Read the newest prior report when useful;
an old manifest or successful connection is historical evidence, not live state.

Match coverage to the request. AI configuration work covers instructions,
client adapters, skills, hooks, MCP discovery and update automation. Product
builds, GitHub fleet scans, dependency sweeps, live sites, transcript mining
and storage cleanup are separate branches, not prerequisites.

## Safe preflight

1. Read shared CONTEXT.md and the closest project instructions. Preserve dirty
   source changes and classify canonical, source-managed, app-owned, system,
   plugin and unknown-origin material before proposing edits.
2. Run `scripts/run-all.sh --selftest`; stop automated script work if it fails.
3. Inspect the relevant script before running it. Prefer narrow read-only checks
   such as maintenance `audit-context.py`, alias reports, overlay `--check` and
   synthetic hook tests. Write outputs in this run directory.
4. Never open protected config, auth, environment or transcript files to audit
   them. Use path/mode/link metadata and safe client-reported status. Do not run
   inventory, mining, stackctl or `run-all.sh` live when their reads violate the
   active policy. Mark the resulting coverage gap explicitly.
5. Record tool/provider availability and configuration scope. A catalog entry,
   parser success or test pass is not authenticated or fresh-client proof.
   Do not start MCP servers just to enumerate them if their launch pins or
   side effects are unknown.

## Review and verification

Read [ground rules](references/ground-rules.md) before delegating and include
them in each brief. Use [workstreams](references/workstreams.md) as an area map;
its historical commands are examples, never authorization to read protected
files or widen scope. Use [finding schema](references/finding-schema.md) for
machine-readable results and stable fingerprints.

Delegate only when the request or active rules authorize it. Use the host's
native orchestration and live provider catalog. A multi-provider request
authorizes that review, not a plan upgrade or unrelated API spend. Keep failed
providers visible and continue independent work; do not repeatedly retry them.
Bound each workstream and give agents distinct ownership.

Every high-impact finding and proposed retirement gets a fresh verifier that
tries to refute it. Inspect actual return values and call paths, not only mocks.
Use [verification](references/verification.md) for larger runs. Confirmed and
adjusted findings lead; refuted and unverified claims remain clearly labeled.
Keep provider-owned caches intact. Do not infer authorship from a missing lock.

## Report, repair and finish

Publish findings and the concrete repair batch before editing. Each repair has
evidence, affected files, verified nonsecret backups, a behavior check, and a
rollback. Change user-owned source, preserve adaptations through the existing
update mechanism, then verify installed parity. Never back up protected files.

Run the relevant behavior suite and inspect the scoped diff. Verify actual
client loading and safe authenticated reads only when available; report missing
access without changing credentials. Do not claim the entire setup is healthy
when provider, OAuth, runtime, or machine coverage remains open.

Use [report template](references/report-template.md) only when it fits the
scope. Link the report and changes; state checks passed, observed failures,
unverified areas and owner actions. Update an existing latest-run link only
after synthesis and only when its ownership is clear.

The legacy full workflow and stackctl are optional audit prototypes. Never
render an old manifest into live configuration. No model-driven audit is
scheduled automatically.
