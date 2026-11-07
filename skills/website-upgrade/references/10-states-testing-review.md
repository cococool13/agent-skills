# States, guards, and review

## Implicit machines

Inventory implicit state in the scoped area: checkout steps, auth sessions, cookie consent, feature flags, form wizards, job/retry status, CMS draft/publish. Write invariants in reader words. Risk-rank them. Check with the lightest tool that can fail: types and tests first; a model checker only if the machine is concurrent, retry-heavy, or crash-sensitive. Trivial loading/empty/error enums get tests, not TLA+.

A model check proves the model, for the states explored, under your constants. Replay counterexamples against the code. Say which rules were not checked.

If `adapters.json` lists `statechart`, use it on high-rank machines; otherwise continue here. It is slash-only, so follow its SKILL.md (path in `adapters.json`). Write the spec in the run folder, never the repo, and run `<statechartCommand> Spec.tla --config Spec.cfg --out <run>/models/<machine>`. The first run fetches TLC and Java through `mise` and needs the network. A spec that uses `+`, `<`, or `<=` must `EXTENDS Naturals`; without it SANY dies with a `NullPointerException`, not a readable parse error.

## Guards

Every confirmed bug gets a proposed or added guard (test, lint, type, or HTTP assertion). Report-only writes the recipe to `proposed-guards.md` when there is at least one guard. Implement mode adds the guard to the repo after fail-then-pass.

Do not delete tests to go green.

## Review and evidence

Independent review means a different person or agent that has not seen your conclusions. If you cannot get that, label `self-review`. Do not call same-agent hat switching independent.

If two artifacts disagree, keep the weaker claim and note the contradiction. On resume, stale fingerprints make earlier findings `STALE`.

When the platform has subagents, spawn the refuter as a fresh agent: give it the report or diff and the code, not your reasoning. That counts as independent review. This skill's evidence types stay authoritative whatever an adapter returns. Run `scripts/validate_findings.py <run>/findings.json` before the report; fix the file, not the validator.

## Browser automation

Use the host's own browser: in Claude Code, the built-in browser pane or Playwright MCP; on Grok Bot, desktop/browser. Local or preview URLs only; never submit a live form. Do not write shell CDP instructions, Playwright installers, or a homemade driver into reports as required steps.

## Roles (same run, different hats)

| Role | Must not do |
| --- | --- |
| Conductor | Invent findings specialists did not support |
| Mapper | Claim unreviewed files were reviewed |
| Threat reviewer | Attack live systems; dump secrets |
| State reviewer | Weaken an invariant to make a model pass |
| Tester | Delete tests to go green |
| Refuter | File new findings (leads only) |
| Implementer | Push, deploy, publish, expand scope |
| Evidence editor | Fill gaps with guesses; relabel self-review as independent |
