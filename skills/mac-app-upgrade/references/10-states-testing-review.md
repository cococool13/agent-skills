# States, guards, and review

## Implicit machines

Inventory implicit state in the scoped area: document dirty/save, window restoration, permission grant/deny/revoke, update check/download/install, sync, pairing, in-flight tasks. Write invariants in reader words. Risk-rank them. Types and tests first; formal models only for concurrent or crash-sensitive machines (update vs quit, two writers on a document). Replay counterexamples against the code. Say which rules were not checked.

If `statechart` is installed, use it on high-rank machines. If it is missing, continue here.

## Guards

Every confirmed bug gets a proposed or added guard. Report-only writes `proposed-guards.md` when there is at least one guard. Implement mode adds the guard after fail-then-pass. Do not delete tests to go green. Prefer tests that use temporary directories, not the user's Library.

## Review and evidence

Independent review means a different person or agent that has not seen your conclusions. Otherwise label `self-review`. Do not call same-agent hat switching independent.

If two artifacts disagree, keep the weaker claim and note the contradiction. On resume, changed fingerprints make earlier findings `STALE`.

If `verify-this` is installed, use VERIFIED / NOT VERIFIED / INCONCLUSIVE; this skill's evidence types remain authoritative.

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
