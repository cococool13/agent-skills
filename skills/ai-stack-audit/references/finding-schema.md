# Finding schema

One JSON object per line in `<workstream>.findings.jsonl`; synthesis merges them into `findings.jsonl`.

```json
{"id":"MCP-007","area":"MCP","title":"...","severity":"P0|P1|P2|P3","impact":1,"effort":"S|M|L",
 "confidence":"high|med|low","evidence":[{"path":"...","lines":"12-18","cmd":"...","observed":"... (redacted)"}],
 "why":"...","fix":"...","trust_level":1,"reversible":true,"needs_approval":true,
 "verified_by":null,"related":["SKL-003"],"rule":"unpinned-npx-launch","fingerprint":"0123456789abcdef"}
```

- `id`: area prefix + 3 digits, unique per run (A=INS, B=SKL, C=MCP, D=PERM/HK, E=PLG, F=PAR, G=LOG, H=SEC, I=MAC, J=GH, K=DEP, L=PRJ-L<n>, M=LIVE, N=LIFE, O=SSOT, P=GAP).
- `evidence[].observed`: never a secret value. Key names, counts, hashes, `file:line` only.
- `rule` (added 2026-10-19 for diffing): short kebab slug of the check that fired. Keep it stable across runs.
- `verified_by`: Wave 3 fills this with `{"agent":"V2","verdict":"confirmed|adjusted|refuted","note":"..."}`.

## Severity
| Sev | Meaning |
|---|---|
| P0 | Security, data loss, or irreversible-action risk (trades, sends, deploys, deletes, secret exposure) |
| P1 | Breaks or blocks work |
| P2 | Waste, friction, or cost |
| P3 | Polish |

## Impact (1-5)
1 cosmetic; 2 minor friction; 3 recurring friction or moderate cost; 4 blocks a workflow or exposes a credential class; 5 irreversible loss, money movement, or account takeover.

## Effort
S under 30 minutes and one file; M a few hours or several files; L a day or more, or a cross-repo change.

## Confidence
high: re-derived from a primary source (file, API, command output) this run. med: inferred from one source or a doc claim. low: plausible, not reproduced.

## Trust level of the fix (prefer the lowest number)
1 code/types/schema/safe default; 2 lint, test, CI, hook, sandbox; 3 instructions or skill; 4 human review. A fix at 3 or 4 must say why it cannot sit higher. A checkable "never/always" rule in prose is itself a finding: "promote to level 1 or 2".

## Ranking
score = impact x confidence weight (high 1.0, med 0.6, low 0.3) / effort weight (S 1, M 2, L 4). Top 10 = highest score among confirmed or adjusted findings. P0s are always listed, whatever the score.

## Fingerprint
`fingerprint = sha256("area|normalized path|rule-slug")[:16]`, all lower case.
Normalize the path: `$HOME` to `~`, drop `:line` suffixes, dates `YYYY-MM-DD` to the literal `YYYY-MM-DD`, `.bak*` suffixes to `.bak*`, no trailing slash. For a URL use scheme+host+path without query. Use the first evidence path.

```bash
python3 -I scripts/report.py --fingerprint MCP "~/.codex/config.toml:12" "unpinned-npx-launch"
```

The 2026-10-19 producers computed fingerprints by hand and did not store `rule`. Next run: recompute today's fingerprints with the canonical function before diffing, or expect most findings to show as new + resolved. `report.py` falls back to computing a fingerprint from area, first evidence path and `rule` (else title) when one is missing.
