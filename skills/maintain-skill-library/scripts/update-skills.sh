#!/bin/bash
# Update source-managed skills, then strip Cursor scan-path copies.
set -euo pipefail
export PATH="/Users/cococool/.nvm/versions/node/v26.4.0/bin:/usr/bin:/bin:/usr/sbin:/sbin"
LOG="${HOME}/Library/Logs/skills-update.log"
mkdir -p "$(dirname "$LOG")"
{
  echo "==== $(date -u +%Y-%m-%dT%H:%M:%SZ) ===="
  npx --yes skills update -g -y || echo "skills update failed (non-fatal)"
  python3 "${HOME}/.agents/skills/maintain-skill-library/scripts/post-update-patches.py"
  python3 "${HOME}/.agents/skills/maintain-skill-library/scripts/prune-cursor-scan-paths.py"
} >>"$LOG" 2>&1
