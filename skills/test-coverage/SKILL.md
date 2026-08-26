---
name: test-coverage
description: "Use when the user asks to run Python tests with coverage or identify untested Python code."
allowed-tools: Bash(pytest:*, uv:*, python:*, make:*), Read, Grep
---

# Python Test Coverage

## Pick the runner from the repo, in this order

1. A `make test` target — `Trading Bot` and `PropScanner` both use one; prefer it.
2. `uv run pytest --cov=src --cov-report=term-missing` — the default for this setup
   (global rules standardize on uv + Ruff + pytest).
3. The repo's own documented command if it differs.

**No project here uses poetry.** Don't run `poetry run` — it will fail with
"command not found" and waste a turn.

## Report

- Overall coverage %, and the delta if a previous run is known.
- The lowest-coverage files, by percentage.
- **Untested lines that matter** — error paths, validation, money/order logic —
  not a flat list of every uncovered line.

Treat coverage as a project-defined gate, not a global percentage target. Do not
add tests purely to raise the number.
