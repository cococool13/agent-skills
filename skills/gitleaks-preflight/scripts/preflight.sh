#!/usr/bin/env bash
# Repo-scoped gitleaks check. Matches Cursor's working-tree scan + git history.
set -euo pipefail

REPO="${1:-.}"
REPO="$(cd "$REPO" && pwd)"
cd "$REPO"

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks: not installed (brew install gitleaks)" >&2
  exit 2
fi

CONFIG=()
if [[ -f "$REPO/.gitleaks.toml" ]]; then
  CONFIG=(--config "$REPO/.gitleaks.toml")
elif [[ -f "$HOME/.config/gitleaks/config.toml" ]]; then
  CONFIG=(--config "$HOME/.config/gitleaks/config.toml")
fi

echo "gitleaks preflight: $REPO" >&2

fail=0

echo "→ git history + staged" >&2
if gitleaks detect "${CONFIG[@]}" -v; then
  echo "  git: clean" >&2
else
  echo "  git: LEAKS — remove or rotate before push" >&2
  fail=1
fi

echo "→ working tree (Cursor uses this for deploy blocks)" >&2
if gitleaks detect "${CONFIG[@]}" --no-git -v; then
  echo "  tree: clean" >&2
else
  echo "  tree: LEAKS — often gitignored locals; run init-config.sh if missing .gitleaks.toml" >&2
  fail=1
fi

if [[ "$fail" -eq 0 ]]; then
  echo "gitleaks: clean"
  exit 0
fi
exit 1
