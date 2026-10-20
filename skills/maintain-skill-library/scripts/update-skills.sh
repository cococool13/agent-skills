#!/bin/bash
# Weekly skills update (LaunchAgent com.cococool.skills-update, Monday 10:00).
# 1. Writes a diff report to ~/Library/Logs/skills-update/<date>.md (locked vs upstream HEAD).
# 2. Updates only lock entries that carry a `ref` (pinned sha), with the pinned local
#    skills CLI (~/.local/share/skills, skills@1.7.2). No -y. Unpinned skills wait for a
#    manual `skills update <name>` after review.
# 3. Restores overlays, then audits the library.
# --dry-run: report and checks only; changes nothing in ~/.agents/skills.
set -euo pipefail

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# Node comes from ~/.local/share/node-current (kept on the nvm default by sync-claude-skills.py).
NVM_NODE_BIN="${HOME}/.local/share/node-current/bin"
export PATH="${NVM_NODE_BIN:+$NVM_NODE_BIN:}/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export DO_NOT_TRACK=1 DISABLE_TELEMETRY=1

MAINTENANCE_DIR="${HOME}/Projects/Agent Skills/skills/maintain-skill-library/scripts"
SKILLS="${HOME}/.local/share/skills/node_modules/.bin/skills"
LOCK="${HOME}/.agents/.skill-lock.json"
LOG="${HOME}/Library/Logs/skills-update.log"
REPORT="${HOME}/Library/Logs/skills-update/$(date +%Y-%m-%d).md"
mkdir -p "$(dirname "$LOG")" "$(dirname "$REPORT")"

run() {
  echo "==== $(date -u +%Y-%m-%dT%H:%M:%SZ) dry_run=${DRY_RUN} ===="
  [ -x "$SKILLS" ] || { echo "pinned skills CLI missing: $SKILLS (npm ci in ~/.local/share/skills)"; return 1; }
  echo "skills=$("$SKILLS" --version) node=$(command -v node || true)"
  python3 "${MAINTENANCE_DIR}/skill-refs.py" report --out "$REPORT"

  update_status=0
  pinned=()
  while IFS= read -r name; do pinned+=("$name"); done < <(jq -r '.skills | to_entries[] | select(.value.ref != null) | .key' "$LOCK")
  unpinned=$(jq -r '[.skills | to_entries[] | select(.value.ref == null) | .key] | join(", ")' "$LOCK")
  echo "pinned: ${#pinned[@]}; waiting for manual review: ${unpinned:-none}"

  if [ "$DRY_RUN" -eq 1 ]; then
    python3 "${MAINTENANCE_DIR}/apply-instruction-overrides.py" --check
    python3 "${MAINTENANCE_DIR}/audit-context.py"
    echo "==== dry run done ===="
    return 0
  fi

  if [ "${#pinned[@]}" -gt 0 ]; then
    "$SKILLS" update -g "${pinned[@]}" </dev/null || update_status=$?
  fi
  python3 "${MAINTENANCE_DIR}/sync-claude-skills.py"
  python3 "${MAINTENANCE_DIR}/post-update-patches.py"
  python3 "${MAINTENANCE_DIR}/apply-instruction-overrides.py"
  python3 "${MAINTENANCE_DIR}/audit-context.py"
  python3 "${MAINTENANCE_DIR}/prune-cursor-scan-paths.py"
  if [ "$update_status" -ne 0 ]; then
    echo "skills update failed; local overlays restored"
    return "$update_status"
  fi
  echo "==== done ===="
}

if [ "$DRY_RUN" -eq 1 ]; then
  run 2>&1 | tee -a "$LOG"
  exit "${PIPESTATUS[0]}"
fi
run >>"$LOG" 2>&1
