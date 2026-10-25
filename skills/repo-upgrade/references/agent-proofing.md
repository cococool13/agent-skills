# Agent-proofing

Goal: the next agent (or person) cannot repeat the mistakes this run fixed.
Make the wrong change fail a check, not depend on someone reading prose.

## 1. Rules as checks

For each rule from lane check 10 that a script can enforce:
- Add it to one small checker (one file for the repo, in the repo's main
  language or a short Python/shell script) plus a test that plants each
  violation and expects it reported.
- Wire it into the local gate, pre-commit (lefthook / pre-commit / husky,
  whichever the repo uses) and the cheapest CI job.
- Fix every current violation in the same commit, or do not add the rule.
- Prefer an existing linter's config over a new script (ESLint
  `no-restricted-imports` / `no-restricted-syntax`, Ruff banned-api, SwiftLint
  custom rules, dependency-cruiser or import-linter for layer boundaries).

Also turn each confirmed bug class into a rule when a pattern can express it
(opengrep/semgrep, ESLint, Ruff), via `semgrep-rule-creator` if present, with
a test fixture holding the original bug. Commit it in the same PR so the class
cannot come back. New rules start as errors only if the tree is clean.

## 2. Cheap strictness

Turn on compiler or linter options that pass today (unused locals and
parameters, `noFallthroughCasesInSwitch`, `-warn-long-expression-type-checking`,
`warnings as errors` in CI only). Each one: gate green before and after.

## 3. Project `verify` skill

Some agents run a project skill named `verify` before committing (recent
Claude Code; check the agent's docs or version first). When the repo has none
and the agent supports it, add `.claude/skills/verify/SKILL.md` (and the
same file under `.agents/skills/verify/` for other agents) with:

1. Run the checks the project has (tests, typecheck, lint, the rule
   checker). If one fails, stop and say exactly where.
2. Review the staged change: one-line summary; prioritize behavior changes,
   data loss and missing edge-case tests; each finding gives the triggering
   input, expected and actual behavior. Only problems you can point to in the
   code. No style.
3. A behavior change that should not happen or possible data loss blocks the
   commit: fix and restart at 1. Other findings are listed and the commit
   proceeds.

If a `verify` skill exists, append missing steps; never overwrite it.

## 4. Deterministic steps into scripts

A sequence an agent repeats (setup, seed, release check) becomes a script
the constraint file names. Leave only judgment in prose.

## 5. Context files

One source of truth for commands and rules (usually `AGENTS.md`); `CLAUDE.md`
and rules files point to it. Remove instructions that name commands or paths
that no longer exist. Keep it short: what the repo is, how to run the gate,
the rules the checker cannot enforce.

## 6. Debt stays visible

Every deliberate limit this run left is a `shortcut: <ceiling>, <trigger>`
comment, so `ponytail-debt` lists it next time.
