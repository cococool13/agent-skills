#!/bin/sh
# The skills-ci gate: lefthook pre-push and .github/workflows/skills-ci.yml both run
# this, so add checks here and not in either caller. test_guard.py takes about a
# minute and needs HOME outside temp roots (the guard treats temp paths as safe).
set -eu
cd "$(git rev-parse --show-toplevel)"
# Git exports GIT_DIR and friends into hooks; test fixtures must not inherit them.
unset $(git rev-parse --local-env-vars)

echo '== Skill frontmatter and listing budget'
# Home entrypoints are machine state, not repo content: a bare audit-context.py checks them.
python3 skills/maintain-skill-library/scripts/audit-context.py --root skills --overlays .ci-none --lock .ci-none --rules .ci-none --agents-md AGENTS.md --listing-root skills --skip-home-entrypoints

echo '== Description overlays: one "Use ..." line, at most 220 characters'
for f in overlays/descriptions/*.txt; do
  line=$(head -1 "$f")
  [ "$(wc -l <"$f" | tr -d ' ')" = 1 ] && [ ${#line} -le 220 ] && [ "${line#Use}" != "$line" ] || { echo "bad overlay: $f"; exit 1; }
done

echo '== Audit tests'
python3 -m unittest discover -s skills/maintain-skill-library/scripts -p 'test_context_audit.py'

echo '== Guard contract tests'
/usr/bin/python3 skills/maintain-skill-library/scripts/hooks/test_guard.py

echo '== repo-upgrade script self-tests'
python3 skills/repo-upgrade/scripts/preflight.py --selftest
python3 skills/repo-upgrade/scripts/scan.py --selftest

echo '== Upgrade skills: package checks and shared-file drift'
# Each skill installs on its own, so shared helpers are copied, not imported. Keep the copies identical.
for s in app-upgrade website-upgrade mac-app-upgrade; do
  out=$(python3 "skills/$s/scripts/validate_skill.py") || { echo "$out"; exit 1; }
done
for f in scripts/parse_invocation.py scripts/fingerprint_run.py scripts/validate_findings.py scripts/validate_skill.py references/evidence.schema.json; do
  for s in website-upgrade mac-app-upgrade; do
    cmp -s "skills/app-upgrade/$f" "skills/$s/$f" || { echo "drift: skills/$s/$f differs from app-upgrade"; exit 1; }
  done
done
# A misspelled --implement must never turn on mutation.
python3 skills/app-upgrade/scripts/parse_invocation.py -- --impl | grep -q '"mode": "report-only"' || { echo 'parse_invocation: --impl enabled implement mode'; exit 1; }
echo 'upgrade skills ok'
