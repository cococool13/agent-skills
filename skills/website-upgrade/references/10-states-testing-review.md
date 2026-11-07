# States, guards, and review

## Implicit machines

Inventory implicit state in the scoped area: checkout steps, auth sessions, cookie consent, feature flags, form wizards, job/retry status, CMS draft/publish. Write invariants in reader words. Risk-rank them. Check with the lightest tool that can fail: types and tests first; a model checker only if the machine is concurrent, retry-heavy, or crash-sensitive. Trivial loading/empty/error enums get tests, not TLA+.

A model check proves the model, for the states explored, under your constants. Replay counterexamples against the code. Say which rules were not checked.

If `statechart` is installed, use it on high-rank machines. If it is missing, continue here.

## Guards

Every confirmed bug gets a proposed or added guard (test, lint, type, or HTTP assertion). Report-only writes the recipe to `proposed-guards.md` when there is at least one guard. Implement mode adds the guard to the repo after fail-then-pass.

Do not delete tests to go green.

## Review and evidence

Independent review means a different person or agent that has not seen your conclusions. If you cannot get that, label `self-review`. Do not call same-agent hat switching independent.

If two artifacts disagree, keep the weaker claim and note the contradiction. On resume, stale fingerprints make earlier findings `STALE`.

If `verify-this` is installed, use its VERIFIED / NOT VERIFIED / INCONCLUSIVE labels; this skill's evidence types remain authoritative.

## Browser automation

Use a host-provided browser adapter if the host already has one. On Grok Bot, desktop/browser is the permitted path. Do not write shell CDP instructions, Playwright installers, or a homemade driver into reports as required steps.

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
