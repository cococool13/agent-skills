---
name: ponytail
description: "Use when /ponytail or the user wants the laziest minimal working solution."
argument-hint: "[lite|full|ultra]"
license: MIT
---
# Ponytail

Deliver the simplest complete solution. Quality includes correct behavior,
readability, security, accessibility, and maintainability; efficiency reduces
unnecessary work without weakening those requirements.

## Choose the implementation

Understand the affected flow and requirements first. Reuse, in order:

1. Existing project code and conventions.
2. Standard-library or native platform features.
3. An already installed dependency.
4. A small implementation of the missing behavior.

Add a dependency only when it removes enough complexity to justify its cost.
Prefer clear code over fewer characters. Keep abstractions, configuration,
compatibility layers, and features tied to an actual requirement.

For a bug, inspect the affected callers and fix the shared cause when appropriate.
Preserve unrelated edits. A smaller diff is useful only if it solves the whole
problem. Do not substitute a partial version for what the user requested.

## Scope and modes

Default: `/ponytail full`. An explicit mode lasts until changed or session end;
“stop ponytail” or “normal mode” ends it.

- `lite`: implement the requested behavior; mention a simpler option only if useful.
- `full`: remove unnecessary complexity within the requested scope.
- `ultra`: challenge speculative extras more aggressively; retain all requested
  behavior and quality requirements.

Modes change how strongly to question extra complexity, not the correctness bar.
Keep a tuning control when a physical system needs calibration. Document a real
limitation where a maintainer needs it; do not add branded comments to routine code.

## Verify and finish

Use focused checks for the behavior changed. Shared behavior, authentication,
payments, data writes, and user-facing flows need coverage of their material failure
cases; there is no one-test ceiling. Avoid tests that only repeat trivial edits.

Edit the files when implementation is requested. Summarize the result, relevant
verification, and real limitations. Match the requested report depth; do not dump
code or invent a “skipped features” section when neither is useful.

## Read-only routes

`/ponytail-review` reviews a diff; `/ponytail-audit` examines the requested scope.
Both report actionable simplifications with file/line, the unnecessary cost, and
a concrete replacement. They do not apply changes unless the user requests fixes.
Keep working code when there is no evidenced improvement. Line-count savings are
optional evidence, not the success criterion.
