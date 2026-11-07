# Example invocation

This file is an example only. It is not part of the generic workflow and does not name a real product.

## Prompt

Use the app-upgrade skill in report-only mode, standard depth, on this iOS app. The app lets one person pick other apps with the system Family Activity picker and apply a Managed Settings shield until a shared condition is met. There is a pairing step between two devices, a local store of the selection, a small API for pairing and status, and a webhook from the billing provider if the user pays for extra features.

Do not push, open a pull request, deploy, or call live billing. Stay on a new local report folder outside the repo.

In addition to the usual inventory and baseline, I want:

1. A threat sketch that includes object-level authorization on pairing records, tenant isolation if one API serves many users, and webhook signature plus replay handling. For the webhook, verify that a valid event is persisted or enqueued durably *before* the handler returns 2xx, that persist failure returns 5xx, and that duplicates fulfill once.
2. An inventory of implicit state machines for pairing, shielding, and authorization revoke, with invariants written in user words and a risk rank. Formally model only the high-risk machines (pairing retries, revoke vs shield). Do not write a TLA+ spec for loading or empty UI. If a TLA+ or statechart skill is installed, use it on the high-rank machines. Replay any counterexample against the code. Say what the model does not prove.
3. A journey matrix for pair, pick apps, apply shield, revoke Screen Time permission, cancel mid-pair, retry after a timeout, and go offline mid-sync.
4. Tests you would add (write them as proposed guards in the run folder) for a double-delivered billing webhook and for a user who changes the object id on `GET /pairs/{id}`. Those may be isolated local fixture tests. Do not probe a live API.
5. Real-device gaps: what the simulator cannot prove about Family Controls tokens and shields. Findings you cannot execute here can still be confirmed with a static path through the code.

If you cannot use a separate reviewer, label the second look as self-review.

## What good output looks like

A run folder outside the repo with:

- `run-meta.json` (commit, dirty digest, config hash, mode, depth)
- `map.md` and `coverage.md` (inspected paths plus explicit gaps; no claim that every file was reviewed)
- `baseline.md`, `threats.md`, `states.md`, `journeys.md`
- `proposed-guards.md`, `evidence.md`, and `findings.json`
- a state note that inventories machines, ranks them, and distinguishes model-check scope from test confidence
- a journey table with no silent blanks
- an evidence pack that lists simulator-only gaps and whether review was independent or self-review

No product-code changes, because this invocation is report-only.

If a later invocation adds `--implement`, the agent creates a branch, adds the proposed guards as in-repo tests first (fail then pass), and still does not push.
