#!/bin/bash
# Update source-managed skills, then strip Cursor scan-path copies.
set -euo pipefail

# Prefer a concrete nvm node; fall back to newest installed, then PATH.
NVM_NODE_BIN=""
if [ -x "/Users/cococool/.nvm/versions/node/v26.4.0/bin/node" ]; then
  NVM_NODE_BIN="/Users/cococool/.nvm/versions/node/v26.4.0/bin"
elif [ -d "/Users/cococool/.nvm/versions/node" ]; then
  newest="$(ls -1 /Users/cococool/.nvm/versions/node | sort -V | tail -1)"
  if [ -n "$newest" ] && [ -x "/Users/cococool/.nvm/versions/node/${newest}/bin/node" ]; then
    NVM_NODE_BIN="/Users/cococool/.nvm/versions/node/${newest}/bin"
  fi
fi
export PATH="${NVM_NODE_BIN:+$NVM_NODE_BIN:}/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

MAINTENANCE_DIR="${HOME}/Projects/Agent Skills/skills/maintain-skill-library/scripts"
LOG="${HOME}/Library/Logs/skills-update.log"
mkdir -p "$(dirname "$LOG")"
{
  echo "==== $(date -u +%Y-%m-%dT%H:%M:%SZ) ===="
  echo "node=$(command -v node || true) npx=$(command -v npx || true)"
  update_status=0
  npx --yes skills update -g -y || update_status=$?
  python3 "${MAINTENANCE_DIR}/post-update-patches.py"
  python3 "${MAINTENANCE_DIR}/apply-instruction-overrides.py"
  python3 "${MAINTENANCE_DIR}/prune-cursor-scan-paths.py"
  if [ "$update_status" -ne 0 ]; then
    echo "skills update failed; local overlays restored"
    exit "$update_status"
  fi
  echo "==== done ===="
} >>"$LOG" 2>&1
