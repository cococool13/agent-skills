# Observability and safe AI-assisted work

## Observability

You should be able to reconstruct what a user did without reading secrets.

- Structured logs with a request or correlation id. One event per decision (accepted, rejected, retried, fulfilled).
- Redact tokens, passwords, webhook signing secrets, personal identifiers, and raw payment payloads. Look at crash reporters and analytics SDKs, not only your own print statements. Quote redacted shapes in the report, not live secret values.
- SLOs belong on user-visible outcomes (successful checkout, successful pair, crash-free sessions), not on "the server was up." If agent-written code does not improve error rates and client regressions, the workflow is wrong. Measure those, not lines of code or PR count.
- A log line that cannot be turned into a replay of the session is weaker than it looks. Prefer enough detail to reconstruct, then stop.

### Recipe: redacted replay

- **Prerequisites:** a log sample from a main flow, with secrets replaced by placeholders.
- **Input:** one successful path and one failure path.
- **Expected fail:** the sample contains a token, raw card payload, or personal identifier; or it cannot explain why a request was accepted or rejected.
- **Expected pass:** a reader can follow the decision from the redacted lines.
- **Artifact:** the redacted sample in the run folder.
- **ROI / stop:** redaction is mandatory before shipping logs off-device. Formal SLO math is overkill before you have traffic; naming the user outcome is not.

## Safe AI coding

Agents copy what already exists, including stale comments and temporary workarounds. Prefer a type, a test, or a lint rule over a comment that explains a hack.

The useful order of investment, from more deterministic to less:

1. Codebase shape: illegal states cannot be represented, boundaries are clear, the easy change is the right change.
2. Mechanical checks: types, lints, tests, CI, model checks.
3. Short prose: `AGENTS.md` or a project skill that a script cannot enforce.
4. Human review, spent on design and on the highest-risk diffs, not on every line an agent produces.

Verification is still an approximation. An agent that "ran the tests" can be as wrong as a person who claimed they did. Require artifacts: command output, failing then passing tests, screenshots or recordings for UI, seeds for simulations.

Do not treat PR volume as quality. A lint rule born from a real bug is quality.

If you generate code with an agent:

- Keep review independent of the authoring context when the change matters. Independent means a different person or agent that has not seen your conclusions. Switching hats in the same session is self-review; label it that way.
- Do not ask the same agent to be the only judge of its own security claims.
- Do not mass-delete comments or tests, and do not invent a duty to keep every comment. Remove narrative leftover comments after you check they do not record a durable external quirk. Replace a wrong test instead of deleting it to go green.

## Stop

You can leave this module when logs from the main flows can be redacted and still explain a failure, and when any agent-driven change in this run produced an artifact a person can replay.
