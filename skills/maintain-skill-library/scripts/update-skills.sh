#!/bin/bash
# Update source-managed skills, restore overlays, then report duplicate aliases.
set -euo pipefail

# Node comes from ~/.local/share/node-current (kept on the nvm default by sync-claude-skills.py).
NVM_NODE_BIN="${HOME}/.local/share/node-current/bin"
export PATH="${NVM_NODE_BIN:+$NVM_NODE_BIN:}/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

MAINTENANCE_DIR="${HOME}/Projects/Agent Skills/skills/maintain-skill-library/scripts"
LOG="${HOME}/Library/Logs/skills-update.log"
mkdir -p "$(dirname "$LOG")"
{
  echo "==== $(date -u +%Y-%m-%dT%H:%M:%SZ) ===="
  echo "node=$(command -v node || true) npx=$(command -v npx || true)"
  update_status=0
  npx --yes skills update -g -y || update_status=$?
  python3 "${MAINTENANCE_DIR}/sync-claude-skills.py"
  python3 "${MAINTENANCE_DIR}/post-update-patches.py"
  python3 "${MAINTENANCE_DIR}/apply-instruction-overrides.py"
  python3 "${MAINTENANCE_DIR}/prune-cursor-scan-paths.py"
  if [ "$update_status" -ne 0 ]; then
    echo "skills update failed; local overlays restored"
    exit "$update_status"
  fi
  echo "==== done ===="
} >>"$LOG" 2>&1
