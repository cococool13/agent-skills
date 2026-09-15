---
name: test-coverage
description: "Use when designing tests, investigating test failures, or improving Python, JavaScript, or TypeScript coverage."

---

# Test coverage

Router for test/coverage work. Open only the language guide you need.

| Language | Guide |
| --- | --- |
| Python | `references/python.md` |
| JavaScript / TypeScript | `references/javascript.md` |

## Shared rules

- Prefer the project's existing scripts and package manager. Do not mix managers or rewrite config unless asked.
- Run the narrowest useful command first; full suite for release gates or shared-code changes.
- Report command, pass/fail, lowest-coverage files that matter, and blockers honestly.
- Coverage is a project gate, not a score to game. Do not lower thresholds to improve a number.
- Browser/E2E QA is `ego-browser`, not this skill. Performance → `optimize`.
