# Testing catalog

Contents: pick the lightest check · examples · property tests · mutation · deterministic simulation · contracts · metamorphic / differential · snapshots · ROI / stop.

Pick the lightest check that would have caught the bug. Record why you skipped the heavier ones.

Report-only and implement mode share the same recipes. Report-only writes the recipe and any transcripts to the run folder (`proposed-guards.md`) and may run existing tests. Implement mode adds the guard to the repo after a fail-then-pass run. Do not confuse "run output lives outside the repo" with "there is no regression check."

## Example and characterization tests

Start here. A failing example with a named input is still the best regression guard for a single bug.

When changing code you do not yet understand, write a characterization (golden master) test that pins current behavior on empty, missing, and boundary inputs, then change the code. Overkill once the behavior is specified and covered.

Fail-then-pass: in implement mode, run the new test with the fix stashed (it must fail) and again with the fix (it must pass). Record both commands.

### Recipe: fail then pass

- **Prerequisites:** implement mode, a new test file or assertion, the fix isolated so you can stash it.
- **Input:** the triggering case from the finding.
- **Expected fail:** the new test fails on current (or stashed) code for the stated reason, not because it cannot compile.
- **Expected pass:** the same test passes with the fix, and the baseline gate is no worse than `baseline.md`.
- **Artifact:** both commands and their output in the run folder; the test in the repo.
- **ROI / stop:** worth it for every bug you fix in implement mode. Stop after that pair of runs; do not add extra suites to decorate the report.

## Property-based tests

State a rule ("decode(encode(x)) == x", "health never exceeds max") and let the library generate inputs. Worth it for codecs, parsers, money math, calendars, and anything with more inputs than you will list. Overkill for a single-branch formatter.

Stateful property tests generate sequences of actions against a model. Use them on the machines from phase 4 that have more sequences than you will write by hand.

- **Prerequisites:** a named property and a generator library the project already has or can add locally.
- **Input:** generated values or action sequences, with shrinking enabled.
- **Expected fail:** a small counterexample that violates the property.
- **Expected pass:** the property holds for the budgeted run; interesting shrinks become fixed example tests.
- **Artifact:** seed, property statement, and any shrunk counterexample.
- **ROI / stop:** skip when you can list the interesting inputs. Stop when shrinking no longer finds new classes of failure.

## Fuzzing

Coverage-guided fuzzing (libFuzzer, cargo-fuzz, OSS-Fuzz style) is worth it on parsers and any code that accepts untrusted bytes. Overkill on a hand-written function with a tight domain. A fuzzer that runs for a while and finds nothing is evidence, not a proof that no crashing input exists.

- **Prerequisites:** a harness that crashes on broken invariants, a corpus directory, a time budget.
- **Input:** untrusted bytes or deeply nested structures.
- **Expected fail:** a crashing input saved as a file.
- **Expected pass:** a quiet budgeted run, with crashing inputs (if any) turned into regression files.
- **Artifact:** corpus path, duration, crashing inputs.
- **ROI / stop:** parsers and untrusted input only, unless the user asked for more.

## Mutation testing

A mutation tester changes the code (flip `<` to `<=`, delete a line) and expects a test to fail. Survivors mean the suite did not notice. Worth it on the files you or an agent just touched, especially when coverage looks high. Overkill as a full-tree nightly for a large app unless you already rely on it. Scope to the diff so it finishes.

Coverage counts executed lines. Mutation testing asks whether those lines were actually checked.

- **Prerequisites:** PIT, mutmut, Stryker, or equivalent, scoped to touched files.
- **Input:** the diff.
- **Expected fail:** surviving mutants on logic you intended to test.
- **Expected pass:** no unexplained survivors in the scoped files (equivalent mutants may be listed, not ignored silently).
- **Artifact:** mutator report.
- **ROI / stop:** the diff, not the monorepo, unless asked.

## Metamorphic tests

When you have no true oracle, check relations: permute input that should not matter, scale an input that should scale the output, or run encode/decode twice. Worth it for search ranking, analytics, compilers, and image or numeric pipelines. Sparse in public discussion compared with property tests. Overkill when a direct assertion exists.

## Differential tests

Run two implementations (old and new, two languages, two browsers) on the same inputs and compare. Worth it for a rewrite or a port. The old program is the oracle. Overkill when there is only one implementation and no reference.

## Snapshot tests

Useful for locking a rendered tree or a serialized fixture you will actually look at when it changes. Brittle when they capture timestamps, random ids, or full page layout that changes for unrelated reasons. Do not treat a huge unmarked snapshot dump as confidence. Prefer snapshots of specific empty, loading, and error states. A snapshot failure is reviewed, not blindly accepted.

## Time, cancellation, races

- Inject a clock. Tests that sleep wall-clock time are slow and flaky.
- Cancel the work and assert it stopped, and that it did not finish later.
- For data races, prefer Thread Sanitizer or equivalent plus a deterministic repro. A test that "usually passes" is not a race test.

## Data, retries, and compatibility

- Migrations: expand and contract (add the new form, dual-write or dual-read, then remove the old form). Never require old clients to understand a breaking schema on the same deploy. Do not run a live migration in this skill; describe the sequence and test it against fixtures.
- Transactions: know the isolation level you actually have. Do not pretend two statements are atomic because they sit next to each other.
- Idempotency: the client sends a key and retries with the same key. The server stores request parameters, locks concurrent retries, keeps a recovery point across foreign calls, and returns the stored result when finished. Keys are scoped per user, expire after a horizon, and reject the same key with different parameters. Local ACID work can often be one transaction. The moment you call Stripe, send email, or publish a queue message, you have a foreign mutation and need phases. Stripe API v1 keeps idempotency keys at least 24 hours, accepts them on `POST`, and ignores them on `GET` and `DELETE`. After the window, reconcile instead of blindly retrying with a new key.
- Outbox: write the business row and the outbound event in the same transaction, then publish asynchronously. This prevents the "database committed, crash before Kafka" hole. It does not give exactly-once delivery to consumers. Consumers still need idempotency.
- Contract tests (Pact or equivalent): worth it when two independently deployed services share a schema. Overkill for a single deployable with in-repo types that already fail the build.

### Recipe: timeout then retry

- **Prerequisites:** an idempotency key (or a clear note that the endpoint is a single local transaction), two fixture callers if the key is scoped per user.
- **Input:** start the request, drop the response, retry with the same key and the same parameters; also retry with the same key and different parameters; also send two concurrent retries.
- **Expected fail:** two charges, two emails, or two published events; or the mismatched parameters silently overwrite the first request.
- **Expected pass:** one side effect and the stored response; mismatched parameters rejected; concurrent retries do not double-apply.
- **Artifact:** test output and the stored key row or equivalent.
- **ROI / stop:** worth it as soon as a retry can duplicate a charge, email, or partner call. Overkill for a read-only endpoint.

## Real-device and environment gaps

Say so when you only ran:

- unit tests on a host that is not the phone or the production OS
- a simulator without Family Controls, push, background modes, or real StoreKit
- a browser instead of the native web view
- a single-thread simulation of a multi-core race

Those gaps belong in the evidence pack.

## Regression guards and comments

After each confirmed bug, add one of: a test with the triggering input, a lint or compiler rule that forbids the pattern, or a typed API that cannot express the illegal state. Wire it into the cheapest local gate. Do not add a rule the tree already violates.

Do not delete tests to go green. If a test is wrong, say why and replace it with a test that pins the intended behavior.

Do not mass-delete comments, and do not keep comments that only narrate the next line. You may remove a comment after you check it does not record a durable external quirk. Prefer a type, test, or lint over a comment that explains a hack.

## Stop

You can leave this phase when every confirmed defect has a guard (proposed in the run folder, and added to the repo in implement mode), the baseline commands still run, and you have listed the techniques you skipped and why.
