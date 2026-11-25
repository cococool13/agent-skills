# CI contract. Agents, the pre-push hook and `ship` all run `just check`.
# Kit: .ci/ (vendored from agent-config ci/; `just ci-drift` shows drift).
# `gate` is scripts/check.sh.
set shell := ["bash", "-euo", "pipefail", "-c"]

# Everything, in parallel.
check:
    .ci/bin/ci-par gate hook-selftests ship-tests library-tests gitleaks

# Changed files since origin/main plus uncommitted work; skips the minute-long suites.
check-fast:
    #!/usr/bin/env bash
    set -euo pipefail
    base="$(git merge-base origin/main HEAD)"
    files="$({ git diff --name-only "$base"; git ls-files --others --exclude-standard; } | sort -u)"
    if [ -z "$files" ]; then echo "check-fast: no changes"; exit 0; fi
    python3 skills/maintain-skill-library/scripts/audit-context.py --root skills --overlays .ci-none --lock .ci-none --rules .ci-none --agents-md AGENTS.md --listing-root skills --skip-home-entrypoints
    if grep -q '^skills/maintain-skill-library/scripts/hooks/' <<<"$files"; then just hook-selftests; fi
    if grep -q '^skills/repo-upgrade/' <<<"$files"; then python3 skills/repo-upgrade/scripts/preflight.py --selftest; python3 skills/repo-upgrade/scripts/scan.py --selftest; fi

# Nothing in this repo has a formatter or autofix.
fix:
    @echo "fix: no formatters configured"

test:
    .ci/bin/ci-par gate hook-selftests ship-tests library-tests

# The skills-ci gate (frontmatter, overlays, audit, guard, repo-upgrade and upgrade-skill tests).
gate:
    scripts/check.sh

# The selftests the lefthook pre-commit runs with the guard tests.
hook-selftests:
    /usr/bin/python3 skills/maintain-skill-library/scripts/hooks/stop-check.py --selftest

# AGENTS.md "Commands".
ship-tests:
    python3 -m unittest discover -s skills/ship/scripts -p 'test_*.py'

library-tests:
    python3 -m unittest discover -s skills/maintain-skill-library/scripts -p 'test_*.py'

# Commits this branch adds, with the repo's .gitleaks.toml.
gitleaks:
    .ci/bin/ci-gitleaks

# Whole history (nightly).
gitleaks-full:
    .ci/bin/ci-gitleaks --full

ci-drift:
    .ci/bin/ci-sync --check .
