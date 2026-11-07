# States, guards, and review

## Implicit machines

Inventory implicit state in the scoped area: document dirty/save, window restoration, permission grant/deny/revoke, update check/download/install, sync, pairing, in-flight tasks. Write invariants in reader words. Risk-rank them. Types and tests first; formal models only for concurrent or crash-sensitive machines (update vs quit, two writers on a document). Replay counterexamples against the code. Say which rules were not checked.

If `adapters.json` lists `statechart`, use it on high-rank machines; otherwise continue here. It is slash-only, so follow its SKILL.md (path in `adapters.json`). Write the spec in the run folder, never the repo, and run `<statechartCommand> Spec.tla --config Spec.cfg --out <run>/models/<machine>`. The first run fetches TLC and Java through `mise` and needs the network. A spec that uses `+`, `<`, or `<=` must `EXTENDS Naturals`; without it SANY dies with a `NullPointerException`, not a readable parse error.

## Guards

Every confirmed bug gets a proposed or added guard. Report-only writes `proposed-guards.md` when there is at least one guard. Implement mode adds the guard after fail-then-pass. Do not delete tests to go green. Prefer tests that use temporary directories, not the user's Library.

## Review and evidence

Independent review means a different person or agent that has not seen your conclusions. Otherwise label `self-review`. Do not call same-agent hat switching independent.

If two artifacts disagree, keep the weaker claim and note the contradiction. On resume, changed fingerprints make earlier findings `STALE`.

When the platform has subagents, spawn the refuter as a fresh agent: give it the report or diff and the code, not your reasoning. That counts as independent review. This skill's evidence types stay authoritative whatever an adapter returns. Run `scripts/validate_findings.py <run>/findings.json` before the report; fix the file, not the validator.

## Driving the app

Exercise flows on a Debug build this run produced, never the copy in `/Applications`, with a temporary data directory. Use the host's desktop-control tool (computer use) or the MobileBuildMCP macOS workflow if the host enabled it. A flow read from code instead of run is labeled `static`.

Do not run or recommend `tccutil reset`, notarization submit, or appcast publish as part of review.

## Roles (same run, different hats)

| Role | Must not do |
| --- | --- |
| Conductor | Invent findings specialists did not support |
| Mapper | Claim unreviewed files were reviewed; assume MAS sandbox without evidence |
| Threat reviewer | Attack live update servers; dump Keychain or Sparkle private keys |
| State reviewer | Weaken an invariant to make a model pass |
| Tester | Delete tests to go green; write fixtures into `~/Library` |
| Refuter | File new findings (leads only) |
| Implementer | Push, ship, notarize, staple, or reset TCC |
| Evidence editor | Fill gaps with guesses; relabel self-review as independent |
