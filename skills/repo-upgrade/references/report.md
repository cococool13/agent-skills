# PR body and reports

## Draft PR body

```markdown
## What this does
<2-3 sentences: the outcome, the biggest fix, the one thing the owner must do.>

## Security
- <confirmed finding, severity, the fix, the regression test>  (from security/REPORT.md)
- Needs validation: <fact owner must check> -> see NEEDS-VALIDATION.md

## Bugs and risk
- <#n title> — case: <input -> wrong result>. Fix: <one line>. Test: <name>, fails before / passes after.

## Speed and scale
- <change> — <command>: <before> -> <after>

## Lean
- Removed <what> (-N lines, -M deps). Proof: <grep / gate>.

## CI
- <change> — <why: cost, speed, safety>

## Rules as checks
- <rule> -> <checker path>, planted-violation test <name>, wired into <gate/pre-commit/CI>

## Verification
- Baseline: <counts>. Now: <counts>. Commands: <list>.
- Could not run here (must run before merge): <list, with toolchain>.
- Not checked: <areas>.
```

## Audit-only / owner report

Use ponytail-audit's output shape for `findings.md`:
`What this repo does:` (2-3 sentences + assumed load), then numbered
findings in Must / Should / Nice, each with **What this is**, **Problem**,
**Fix**, **If we skip it**, then `Verdict:`, `Lean: -N lines, -M deps
possible.`, `Not checked:`. Prepend a one-line security summary (count of
confirmed by severity, count needing validation) and link `security/REPORT.md`.
With prior runs, add `Since last run: X resolved, Y still open, Z new.`
