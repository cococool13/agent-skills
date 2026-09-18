---
name: optimize
description: "Use when making code, config, or a script faster, simpler, or less costly to run."
---
# Optimize

Improve the named code, configuration, or script while preserving required
behavior. Prefer a clear, maintainable solution over clever compression.

## Find the cost

Identify the affected flow and its callers. Look for repeated work, unnecessary
I/O or allocations, expensive algorithms, and contradictory or duplicate settings.
For prompts, consider both loading cost and whether the instructions cause extra
work. Evaluate interacting files together rather than optimizing each in isolation.

Use measurements when claiming a runtime improvement. Static analysis can identify
likely costs; label those conclusions as estimates. Do not add a benchmark harness
for a trivial simplification or a one-off helper that existing tools can cover.

## Make the change

- Prefer removing unnecessary work to adding machinery around it.
- Reuse project code, the standard library, and existing dependencies first.
- Keep changes within scope and preserve unrelated edits and configuration.
- Preserve observable behavior, failure handling, and relevant edge cases. If the
  requested optimization needs a tradeoff, explain it before changing the contract.
- Edit files when implementation is requested; keep an audit-only request read-only.

## Verify and report

Run the checks appropriate to the affected behavior. Compare the same workload
before and after when performance is the claim. Do not describe static complexity
analysis as a measured speedup.

Lead with the result, explain the substantive change, and state verification and
remaining limitations. Show a before/after table only when useful evidence exists.
Return a code block when the input was a standalone snippet or the user asks for it;
do not paste an entire changed file by default.
