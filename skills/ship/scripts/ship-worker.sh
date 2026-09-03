#!/usr/bin/env bash
# Current-repo ship + gitleaks + wrangler deploy + optional verify script.
set -euo pipefail

ROOT="$(git -C "${1:-.}" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT" ]]; then
  echo "ship-worker: not inside a git repo" >&2
  exit 1
fi
cd "$ROOT"

python3 "${HOME}/.agents/skills/ship/scripts/ship.py" --apply --fast
bash "${HOME}/.agents/skills/gitleaks-preflight/scripts/preflight.sh" "$ROOT"

if [[ -f worker/wrangler.jsonc ]]; then
  (cd worker && npm run deploy)
  if [[ -x scripts/verify-worker.sh ]]; then
    scripts/verify-worker.sh
  fi
elif [[ -f wrangler.jsonc ]]; then
  npm run deploy
else
  echo "ship-worker: no wrangler.jsonc at repo root or worker/" >&2
  exit 1
fi

echo "ship-worker: done"
