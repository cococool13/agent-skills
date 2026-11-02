# Wave 3: verification

Synthesis reads only findings that a fresh agent re-derived. Producers never verify their own work.

## Selection (deterministic; `scratch/merge-findings.py` pattern)
1. All P0s.
2. Top 25 non-P0 findings by impact x confidence.
3. Every finding whose title or fix proposes delete, archive, remove, uninstall, retire or reclaim.
4. Dedupe by fingerprint. Log what the cap dropped; no silent truncation.

## Verifier agents
- 4-6 verifiers, 5-10 findings each, grouped by area so one agent can reuse context. A verifier never gets findings from a workstream it produced.
- Each gets: ground rules word for word, the finding JSON, and "re-derive the evidence with new commands; do not trust the observed field; try to refute first".
- Read-only, same tool limits as Wave 1. Budget about 40 tool calls each.
- Strongest model, medium-high effort. These verdicts gate the top 10.

## Red-team verifier (exactly one)
Two jobs:
1. What did the audit miss? Pick the 3 areas with the fewest findings and probe them.
2. Which recommendations would break something? Examples: a deny rule that blocks a hook's own read, a pin that breaks a skill's script, a sandbox profile that breaks `xcodebuild` or `wrangler dev`, an `ask` on a tool a LaunchAgent calls headlessly.
Output: new findings (normal schema, `verified_by` null so the next run checks them) plus `breaks` notes attached to existing IDs.

## Verdict schema (one line per finding in `verify/V<n>.jsonl`)
```json
{"id":"MCP-001","fingerprint":"...","verdict":"confirmed|adjusted|refuted",
 "evidence":[{"cmd":"...","observed":"... (redacted)"}],
 "adjust":{"severity":"P1","impact":3,"fix":"..."},
 "note":"one or two sentences","breaks":["what the fix would break, if anything"]}
```
`adjust` only when the verdict is adjusted. Synthesis writes `verified_by` back into `findings.jsonl`.

## Rules for synthesis
- Only confirmed or adjusted findings reach the top 10 and quick wins.
- Refuted findings go to an appendix with the verifier's reason.
- Unverified findings stay in the full appendix, marked unverified.
- A `breaks` note downgrades the fix to "needs design" until resolved.
