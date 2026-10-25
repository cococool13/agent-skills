# Deterministic tools and optional companions

## Scanners (`scripts/scan.py` runs whichever are installed)

All read-only and offline (Go/Cargo network off), 300 s timeout each. Only knip and jscpd may run from the repo's `node_modules/.bin`. Output goes to `<run>/scans/`. Hits are leads: verify each
against source before it becomes a finding (`verify.md`).

| Stack | Tool | Command scan.py runs | Caveat |
| --- | --- | --- | --- |
| JS/TS | knip | `knip --reporter json --no-exit-code` | never `--fix`; dynamic imports and plugin gaps cause misses |
| JS/TS | jscpd | `jscpd . --reporters console --min-tokens 50 --silent` | generated code and tests inflate clones |
| Python | vulture | `vulture . --min-confidence 80` | frameworks, getattr, dynamic dispatch |
| Python | deptry | `deptry .` | import name != distribution name needs mapping |
| Go | deadcode | `deadcode -test ./...` | RTA from main; libraries show little |
| Go | govulncheck | `govulncheck ./...` (`--online` only) | downloads its database; reachability-aware |
| Rust | cargo-machete | `cargo machete` | renamed crates give false positives (`--with-metadata` fixes it but may touch the network) |
| Swift | periphery | `periphery scan` (only if `.periphery.yml` exists; it builds) | use `--retain-public` for frameworks |
| Any | osv-scanner | `osv-scanner scan source -r . --format table` (`--online` only) | sends the dependency list to api.osv.dev; any vulnerable version, reachable or not; never `fix` |
| Any | gitleaks | `gitleaks git --redact --no-banner .` | feature-frozen upstream (betterleaks is the successor); use `--baseline-path` on re-runs |
| Any | opengrep / semgrep | `opengrep scan --config .semgrep --text .` (only if `.semgrep/` exists; falls back to `semgrep`) | Cloudflare found agents rarely call it on their own, so pre-run it |
| CI | zizmor | `zizmor --offline --min-confidence=medium .github/workflows` | `--fix` writes files |
| CI | actionlint | `actionlint` | ignore unknown self-hosted labels |
| CI | pinact | `pinact run --check --no-api` | `--verify-comment` for tag/SHA mismatch |
| Any | scc | `scc --no-cocomo` | complexity is a heuristic; for sizing lanes |
| Any | lizard | `lizard -C 15 -w .` | flags functions over CCN 15 |

Not run by scan.py (slow or writes state), use on demand:
- trufflehog `trufflehog git file://. --results=verified --json` contacts
  providers to verify secrets. Ask first.
- Benchmarks: `hyperfine --warmup 3 --export-json <out> '<cmd>'` before and after.
- Mutation testing on changed files only: `npx stryker run --incremental`,
  `mutmut run`, `cargo mutants -f <file>`. A new test that kills no mutant of
  the fixed code is not proving the fix.
- dependency-cruiser / import-linter for layer rules (phase 6).

Missing tools are listed in `scans/summary.md` with the install line; do not
install them without a yes.

## Optional companions (used when preflight finds them)

Checked against upstream, Oct 2026. Read by path like the core companions.

| Companion | Source | Where it plugs in |
| --- | --- | --- |
| `fp-check` | trailofbits/skills | refuter for high and critical security claims from the fallback lane |
| `supply-chain-risk-auditor` | trailofbits/skills | dependency risk beyond CVEs (abandoned, install scripts, yanked) |
| `agentic-actions-auditor` | trailofbits/skills | prompt-injection paths into AI steps in GitHub workflows (CI lane) |
| `variant-analysis` | trailofbits/skills | after a confirmed bug, sweep for siblings |
| `semgrep-rule-creator` | trailofbits/skills | turn a confirmed bug class into a rule (phase 6) |
| `mutation-testing` | trailofbits/skills | triage surviving mutants on fixed code |
| `post-patch-validation` | trailofbits/skills | adversarial check of security fixes before the PR |
| `differential-review` | trailofbits/skills | extra self-review pass with blast radius by caller count |
| `improve-codebase-architecture` | mattpocock/skills | report-only architecture lane on `--deep` |
| `deslop` | brianlovin/claude-config | strip agent slop from this run's own diff before review |

Install (Claude Code): `/plugin marketplace add trailofbits/skills` then
`/plugin install <name>`; other agents: `npx skills add trailofbits/skills
--skill <name> -g`. Ask first.
