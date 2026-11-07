# State machines and verification

## Find the machines

Search for status fields, step counters, paired booleans (`isConnected` plus `isConnecting` plus `hasError`), retry flags, and multi-screen flows. Typical machines: onboarding, pairing, purchase, sync, permission prompts, background refresh, and "this job is running."

If two booleans can form an illegal combination, that combination will appear. Make illegal states unrepresentable with a single enum or a sum type before you add more tests.

Write each rule in the words of a person who uses the product: "a ride is never charged twice," "a shield is never applied after authorization is revoked," "a canceled request does not fulfill later."

Inventory *every* in-scope machine, including the small ones. Then risk-rank them. Do not write a formal spec for every enum you find.

### Risk rank

| Rank | Signals | Default check | Formal model? |
| --- | --- | --- | --- |
| High | money, two writers, retries, crashes, networks, pairing/sync, entitlements that unlock enforcement | types, transition tests, then a model checker or deterministic simulation if the runtime allows it | Yes when interleavings or recovery can hide a bug |
| Medium | multi-step wizards, permission prompts, purchase restore | types plus hand-written cancel/retry transitions | Only if `--deep` *and* two parties or retries can interleave |
| Low | idle/loading/empty/error, single-form CRUD, cosmetic animation | an explicit enum and UI or unit tests | No, even in `--deep` |

`--deep` means the inventory and the ranking are complete, not that every row gets TLA+ or `statechart`.

### Recipe: inventory and rank

- **Prerequisites:** `map.md` from phase 1.
- **Input:** the flags, status columns, and multi-step flows in scope.
- **Expected fail:** two booleans that can be true together illegally, or a high-risk flow with no written invariant.
- **Expected pass:** each machine has states, transitions, an owner, invariants in user words, a rank, and a chosen check.
- **Artifact:** `states.md` in the run folder.
- **ROI / stop:** inventory is worth it whenever behavior is spread across flags or screens. Stop listing when a search for status enums, paired booleans, and wizard step numbers adds no machine. Stop *modeling* when only low-rank UI remains.

## Choose a tool, lightest first

1. Types and assertions in the production language. Worth it almost always.
2. Example tests for each transition, including cancel and retry. Worth it for every machine users depend on.
3. Property-based or stateful tests that generate sequences of actions and check the invariant. Worth it when the machine has more sequences than you will write by hand. Overkill for a three-state enum with no concurrency.
4. A model checker (TLA+, PlusCal, Quint, Alloy, or a project skill from `create-formal-verification-skill`) or the installed `statechart` skill. Worth it when concurrency, retries, crashes, or two writers can interleave. Overkill for a pure function or a CRUD form with no shared state.
5. A proof assistant (Lean, Rocq, Isabelle, Dafny, Verus). Worth it for a tiny, stable, mission-critical core. Overkill for ordinary application code. Proofs are expensive and still relative to the spec you wrote.

Hillel Wayne's distinction, which this skill treats as a rule: unit tests, property tests, model checking, proofs, and deterministic simulation are different tradeoffs. They are not a ladder from "amateur" to "correct."

Amazon's published TLA+ work (CACM, 2015) is the usual industrial reason to bother: model checking found long interleavings that reviews and tests missed. Those were design bugs. Amazon is explicit that a checked model is not the executable system, and that showing the code implements the model is a separate, often unavailable, step.

## What a model check actually proves

A model checker explores the model you wrote, under the constants, constraints, views, and symmetries you set.

It can prove that every explored state satisfies the invariants and (for a complete run) that there is no deadlock in the model. It cannot prove:

- that the model matches the code
- that a constant you bounded (three users, two retries) behaves the same at production scale
- that a rule listed under "not checked" after a bound or an earlier broken invariant still holds
- anything about hardware, the operating system, or a dependency you abstracted away

If you model `if (x == 0) x = x + 1` as one atomic step, the checker cannot see the race between the test and the assignment. That missed bug is a modeling error, not a proof of safety. Wayne reports running a two-thread version of that race 100,000 times without seeing it, then finding it immediately once the `if` and increment were separate model steps.

### Running `statechart`

It is slash-only, so follow its SKILL.md (path in `adapters.json`) rather than the Skill tool. Write the spec and config in the run folder, never the repo, then run `<statechartCommand> Spec.tla --config Spec.cfg --out <run>/models/<machine>`. The first run fetches TLC and Java through `mise` and needs the network; later runs are offline. A spec that uses `+`, `<`, or `<=` must `EXTENDS Naturals` (or `Integers`); without it SANY dies with a `NullPointerException` in the XML exporter, not a readable parse error. Copy `report.md` and `chart.mmd` into `states.md`.

When `statechart` or TLC reports a broken rule, replay that path against the real code, one action at a time. If the code does not fail, assume the model is wrong until you show otherwise. When `statechart` is installed, follow its own rules: do not weaken an invariant to make it hold, label states in the reader's words, and keep charts small enough to read.

"Formally verified" does not mean "bug-free." Anthropic's October 22, 2026 note says the same: a proof is relative to the spec and the machine model you trusted.

### Recipe: model check and replay

- **Prerequisites:** a high-rank machine, written invariants, small constants, and a checker you actually have (or skip and say so).
- **Input:** the model plus one invariant in user words.
- **Expected fail:** the checker finds a trace, or a replay shows the code does not match the model.
- **Expected pass:** the bounded run holds, every counterexample is marked "reproduced in code" or "model bug," and unchecked rules are listed.
- **Artifact:** model file, checker output, bounds, and replay notes in the run folder.
- **ROI / stop:** worth it for high-rank machines. Stop if the checker hits a bound you cannot raise usefully, and list what stayed unchecked. Do not spend the budget modeling a loading spinner.

## Deterministic simulation and fault injection

Deterministic simulation testing (DST) runs the real code with a fake clock, network, and disk, so a seed plus a commit hash replays a failure. FoundationDB's simulator and TigerBeetle's VOPR are the reference designs. Antithesis applies the same idea with an external hypervisor when you cannot make the whole program deterministic yourself.

Worth it when the system is concurrent, distributed, or crash-sensitive, and you can isolate I/O. Overkill for a request that does one database write and returns.

A simulation that finds no bug after a bounded time is evidence, not a proof. It is much stronger evidence than hoping the operating system scheduler hits the one-instruction race window.

If full DST is out of reach, you can still:

- inject a fake clock (never call "now" directly in domain code)
- cancel tasks and assert that work stops
- fail the network or disk on the next call
- replay a recorded input log

Record the seed, the commit, and the command for every interesting run.

### Recipe: seed replay

- **Prerequisites:** clock/network/disk seams, or an existing simulator.
- **Input:** a seed, a commit, and the faults you inject (drop, reorder, partition, crash, corrupt).
- **Expected fail:** an invariant breaks and you cannot replay from the seed.
- **Expected pass:** the failure (or a clean bounded run) replays from the same seed and commit.
- **Artifact:** seed, commit, command, and checker notes.
- **ROI / stop:** worth it for sync, consensus, crash recovery, and retry protocols. Stop after a stated wall-clock budget. A quiet run is evidence, not completeness.

## Stop

You can leave this phase when every in-scope machine is inventoried and ranked, each invariant has a check at some level above, high-rank machines have more than hope-and-review, and every model-checker counterexample has been replayed or marked as a model bug.
