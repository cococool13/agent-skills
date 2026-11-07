# Review, evidence, and adapters

## Independent review versus self-review

After implement mode (or after a large report), have a reviewer who did not write the findings read the diff or the report.

Independent review means a different person or agent, with a different context window, that has not seen your conclusions. They should try to disprove each Must-fix: find the guard, the caller, or the config that makes it impossible. Keep claims that still hold with a concrete case. Drop the rest, or downgrade them.

If you cannot spawn or ask a separate reviewer, switch hats yourself and label the pass `self-review` in the evidence pack. Self-review is better than no second look. It is not independent review. Do not describe same-agent role switching as independent, adversarial, or "fresh eyes."

A shallow independent review that returns zero findings faster than its peers deserves one rerun before you trust "nothing found."

When the platform has subagents, spawn the refuter as a fresh agent: give it the report or diff and the code, not your reasoning. That counts as independent review.

`interrogate` and `arena` (pstack, slash-only) run many agents at once. Use them only when the user named them; otherwise recommend `/pstack:interrogate` for the Must-fix list in the report. Style opinions and unimplemented future risks are out of scope for that pass.

Command reproduction is preferred. It is not the only acceptable evidence. A security finding that you cannot run here (Family Controls on a simulator, a webhook you must not hit live, a missing toolchain) may still be `confirmed-static` if you write the path: entry point, controlled input, missing or weak control, resource, impact, and file references. Do not drop those findings, and do not mark them `confirmed-repro`.

If `adapters.json` lists `blast-radius`, read and follow it when a small diff might break something search will not show. Prove the one fact the change is safe because of by running code.

If `ponytail-review` is listed, apply it to `git diff <base>...HEAD`.

This skill's evidence types (`confirmed-repro`, `confirmed-static`, `opinion`, `needs-validation`) stay the record of record whatever an adapter returns. Run `scripts/validate_findings.py <run>/findings.json` before the report; fix the file, not the validator.

At most two independent review-and-fix rounds. Self-review does not consume those rounds.

## Resume and stale evidence

`run-meta.json` must include the fingerprint from `scripts/fingerprint_run.py` (commit, branch, dirty digest, config hash, scoped path, mode, depth). On resume, rerun the script. If commit, dirty digest, scoped path, or config hash changed, mark earlier checkpoints and findings `STALE` and redo the checks those files depended on. Do not treat a transcript from a different tree as fresh evidence.

If two artifacts disagree (for example `findings.json` says `confirmed-repro` and the saved command output is missing or shows a pass), keep the weaker claim and note the contradiction. Do not silently pick the stronger label.

## Evidence pack

Write `evidence.md` and `findings.json` in the run folder. `findings.json` follows `references/evidence.schema.json`.

`evidence.md` includes:

- Scope, mode, depth, and the fingerprint summary.
- Commands you ran and their results, copied rather than summarized when the result is a number or a failure.
- Findings, each with a case, an evidence type, and a proposed or added guard.
- The state-machine inventory and risk rank, plus model-check bounds and rules that were not checked.
- Simulation seeds.
- Real-device, paid-API, and toolchain gaps.
- Compatibility notes: which clients you proved still work, and which you did not.
- Whether review was independent or `self-review`.
- Coverage gaps copied or linked from `coverage.md`.
- Stale or contradictory artifacts, if any.
- What you did not look at.

Also write `proposed-guards.md` in report-only mode. Each entry uses the recipe shape (prerequisites, input, expected fail, expected pass, artifact, ROI/stop). In implement mode, link those entries to the files you added in the repo.

Never convert a guess into a confirmed finding to fill a section.

## Roles (same run, different hats)

Use different hats so one pass does not grade its own homework. When the platform allows it, the refuter is a different agent or person from the hunter.

| Role | Job | Must not do |
| --- | --- | --- |
| Conductor | Sequence phases, keep scope, write checkpoints | Invent findings the specialists did not support |
| Mapper | Inventory, coverage, journeys | Decide severity alone; claim unreviewed files were reviewed |
| Threat reviewer | Trust boundaries | Attack live or shared systems; dump secrets |
| State reviewer | Invariants and models | Weaken an invariant to make the model pass; force a formal spec on a trivial UI enum |
| Tester | Tests, fuzz, mutation, simulation | Delete tests to go green |
| Refuter | Try to disprove each Must-fix | File new findings (leads only) |
| Implementer | Smallest complete fix, in implement mode only | Push, deploy, expand scope, revert unrelated user edits |
| Evidence editor | Assemble the report from commands that actually ran and static paths that were traced | Fill gaps with guesses; relabel self-review as independent |

## If a `repo-upgrade` skill is installed

You may delegate baseline scanning, audit lanes, and a fail-then-pass fix ladder to it. Pass its audit-only mode unless the user asked to implement. Still run this skill's threat, state, journey, and testing-catalog phases, because that conductor may not treat them as first-class. Still obey this skill's rule against implicit push or pull request. Ignore any house step that would open a draft PR, merge, deploy, or migrate unless the user named that action.

House extras such as a Cloudflare security audit belong only if that conductor actually provides them. Do not invent the command.

## Compatibility

Preserve the current branch until you create a working branch in implement mode. Do not retarget other people's branches. Do not merge. Do not delete a public identifier because it looks unused in a shallow clone.

When discarding a failed fix, revert only your isolated changes for that attempt and keep the diff plus failing output in the run folder.
