# Verify

Agents return claims. Only verified claims reach `findings.md`, and only
those get fixed.

## For every finding you intend to report or fix

1. Re-read the cited lines yourself. Confirm the caller exists, the value can
   really be empty, the path is reachable from an entry point in `map.md`.
2. Write the concrete case: input or situation -> wrong result. No case, drop it.
3. Unused code: grep the whole tree (tests, fixtures, config, scripts, string
   and dynamic references, reflection, framework conventions like route
   files) before calling it dead. A scanner saying "unused" is a lead.
4. "Redundant" code: find the test that pins it and run that test first.
5. A `shortcut:` marker naming its limit is a decision unless the expected
   load already crosses it.

## Refuter agents

Send each Must-fix and each security claim from a lane to a fresh agent that
has not seen the audit. Brief it with the claim, the code paths, and:
"Try to disprove this. Look for the guard, caller, config or invariant that
makes it impossible. Return refuted / holds / needs_validation with the
evidence line and a 0-100 confidence." Batch up to 5 related claims per
refuter. Drop refuted claims and anything under 80. Disagreement you cannot
settle from source becomes `needs_validation`.

- The refuter only judges; it never files new findings (it may note a lead
  for the next run).
- Use a different model from the hunters when the platform allows it, so
  they do not share blind spots. `fp-check` (if present) handles high and
  critical security claims from the fallback lane.
- Dedupe by root cause, not by title or file.
- A lane that returns zero findings or finishes far faster than its peers
  is a shallow run: re-run it once before trusting "nothing found".
- Keep each agent's brief and reads well under its context window; split a
  lane rather than let it compact.

Security false-positive filter (from Anthropic's security-review): unless the
claim shows a concrete boundary violation, drop generic DoS or resource
exhaustion, missing rate limits, input validation without proven impact,
open redirects, and theoretical race conditions.

Cloudflare records are already refuted and independently verified; do not
re-litigate `confirmed` records, only check that the cited lines still match
the current source.

## Proving a fix

- Fail-then-pass: run the new test with the fix stashed (must fail), then
  with it (must pass). Record both commands and results in the commit body.
- Refactors: list old behavior on empty, missing and boundary inputs before
  the change and assert it after.
- Optimizations: the same command before and after (e.g. `hyperfine`), with
  the numbers in the commit body. Small wins without numbers are suggestions.
- Deleted code: gate passes, plus the grep evidence in the commit body.

## Drop list

Style taste, "consider", vague worries, generic best practice with no
reachable failure, guessed deployment behavior, self-impact, checklist gaps.
