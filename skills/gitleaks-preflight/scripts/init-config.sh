#!/usr/bin/env bash
# Copy standard .gitleaks.toml into the current repo if missing.
set -euo pipefail

REPO="${1:-.}"
REPO="$(cd "$REPO" && pwd)"
DEST="$REPO/.gitleaks.toml"
TEMPLATE="${HOME}/.agents/skills/gitleaks-preflight/templates/gitleaks.toml"

if [[ -f "$DEST" ]]; then
  echo "exists: $DEST"
  exit 0
fi

if [[ ! -f "$TEMPLATE" ]]; then
  echo "missing template: $TEMPLATE" >&2
  exit 1
fi

cp "$TEMPLATE" "$DEST"
echo "created: $DEST"
echo "Review path allowlists, then commit."
