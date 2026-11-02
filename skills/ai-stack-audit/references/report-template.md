# REPORT.md skeleton

Write `REPORT.md`, `findings.jsonl` (all findings with fingerprints and `verified_by`), `metrics.json` (every scorecard number) and `baseline.json`. The next run diffs these.

```markdown
# AI stack audit YYYY-MM-DD

## 1. Executive summary
<=12 lines: state of the stack in one paragraph; 3 biggest risks; 3 biggest wins.
Diff vs previous run: N new, N resolved, N regressed (from `report.py --diff`).

## 2. Scorecard
| Area | Score 0-10 | Trend | Basis |
|---|---|---|---|
Instructions, Skills, MCP, Permissions/sandbox/hooks, Secrets, Supply chain, Cross-agent parity,
Context efficiency, Reliability (tool-error rate), Cost efficiency, Mac toolchain, GitHub hygiene,
Project health, Live product quality, Backup/data safety, Automation leverage.
Trend = arrow vs previous `metrics.json` (first run: "baseline").

## 3. Top 10 fixes (verified only)
| # | ID | Fix | Evidence | Trust | Reversible | Effort | Expected effect |
Ranked by impact x confidence / effort. Expected effect is measurable ("-4.1K always-on tokens").

## 4. Quick wins
Under 10 minutes, reversible, no approval risk.

## 5. Proposed deletions / archives
| Item | Reason | Depends on it | Undo | GB |
Proposals only; each needs Cohen's OK.

## 6. Blast radius before / after (from H)

## 7. Cost and effectiveness
Spend by project, model, week; cache-hit rate; waste patterns; model-routing policy.

## 8. Cross-agent parity matrix + single-source-of-truth design (from F, O)

## 9. Gap analysis vs benchmarks (from P)

## 10. Per-project and per-site tables (from L, M)

## 11. Appendices
Full findings (all IDs); refuted findings with reasons; open questions; not checked and why.
```

`metrics.json` shape (flat numbers so `report.py` can diff them):
```json
{"scores": {"Instructions": 7, "MCP": 4},
 "reliability": {"tool_error_rate_pct": 6.1},
 "cost": {"usd_30d": 3485, "cache_hit_pct": 98.6},
 "counts": {"findings": 404, "p0": 20}}
```
