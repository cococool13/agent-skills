---
name: javascript-test-coverage
description: "Use when the user asks to run, assess, fix, or improve JavaScript or TypeScript tests or coverage."

---

# JavaScript Test Coverage

## Start with the project truth

1. Read the nearest `AGENTS.md` or `CLAUDE.md`, then inspect `package.json`, the lockfile, and the existing test/coverage configuration.
2. Select the package manager from the lockfile. Do not mix package managers, install dependencies, add coverage providers, or rewrite test configuration unless the user explicitly asks.
3. State the success check before modifying code. For a reproducible failure, run the smallest reproduction before and after the change.

## Run the narrowest useful command

- Prefer an existing `test`, `test:unit`, `test:coverage`, `coverage`, `check`, or project-documented script.
- Run a targeted file or test name when the request names a feature, file, or failure. Use the full suite only for a release gate, shared-code change, or explicit request.
- If the project uses Vitest and exposes no coverage script, inspect the installed configuration before proposing a coverage command. Never assume a provider is installed.
- Keep end-to-end and visual-browser verification separate. Hand browser behavior or screenshots to the project's Playwright/browser workflow.

## Read the result honestly

Report:

- the command and scope that actually ran;
- pass/fail totals and any configured coverage threshold;
- the lowest-coverage production files and the highest-value untested paths;
- the exact blocker when tests or coverage cannot run.

Treat changed behavior as unverified until the relevant tests pass. Do not claim full coverage from a partial run, and do not lower thresholds, exclude files, or silence failures merely to improve a number.

## Boundaries

- For Python, use `test-coverage`.
- For performance profiling, use `optimize`.
- For security review, use the security workflow rather than treating coverage as a substitute.
