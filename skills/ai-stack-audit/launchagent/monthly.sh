#!/bin/bash
# monthly.sh - wrapper for com.cococool.ai-stack-audit-monthly (PROPOSAL, PLAN B13).
# launchd fires every Monday 09:00 local time; this exits unless the day is 1-7 (first Monday).
# Runs run-all.sh only: no claude -p, no codex exec, no model tokens, no mutations.
# Posts a one-paragraph summary: SUMMARY.md in the run dir + a macOS notification.
# Manual test: AI_AUDIT_FORCE=1 bash monthly.sh
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.local/share/node-current/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOMEBREW_NO_AUTO_UPDATE=1
DAY=$((10#$(date +%d)))
if [[ "${AI_AUDIT_FORCE:-0}" != "1" && $DAY -gt 7 ]]; then exit 0; fi

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REVIEW="$HOME/Projects/_review"
RUN="$REVIEW/ai-stack-audit-$(date +%F)/cron"
PREV="$(readlink "$REVIEW/ai-stack-audit-latest" 2>/dev/null || true)"
URLS=""; [[ -n "$PREV" && -f "$PREV/workstreams/M.urls.json" ]] && URLS="$PREV/workstreams/M.urls.json"

mkdir -p "$RUN"
set +e
bash "$SKILL/scripts/run-all.sh" --run-dir "$RUN" ${PREV:+--prev "$PREV"} ${URLS:+--urls "$URLS"} > "$RUN/monthly.log" 2>&1
rc=$?
set -e

inv="$RUN/inventory.json"; gh="$RUN/gh-fleet.json"
perm="$(jq -r '.claude.permissions | "allow \(.allow) / ask \(.ask) / deny \(.deny)"' "$inv" 2>/dev/null || echo 'n/a')"
skills="$(jq -r '.skills.agents.entries // "n/a"' "$inv" 2>/dev/null || echo n/a)"
broken="$(jq -r '[.skills[]? | objects | .broken_links] | add // 0' "$inv" 2>/dev/null || echo n/a)"
alerts="$(jq -r '.totals.open_alerts | "\(.critical) critical, \(.high) high"' "$gh" 2>/dev/null || echo 'n/a')"
drift="$(grep -c . "$RUN/stackctl-check.txt" 2>/dev/null || echo 0)"
mcp="$(head -1 "$RUN/mcp-diff.txt" 2>/dev/null || echo 'MCP diff not run')"
write="$(grep -m1 '^write-check' "$RUN/run-all.log" 2>/dev/null || echo 'write-check missing')"
status=$([[ $rc -eq 0 ]] && echo "ok" || echo "exit $rc")

para="AI stack monthly check $(date +%F) ($status). Permissions $perm; $skills skills, $broken broken links; Dependabot open alerts $alerts; stackctl drift lines $drift; $mcp; $write. Full output: $RUN. Run /ai-stack-audit for the model-driven audit."
printf '# AI stack monthly check %s\n\n%s\n' "$(date +%F)" "$para" | bash "$SKILL/scripts/redact.sh" > "$RUN/SUMMARY.md"
ln -sfn "$RUN" "$REVIEW/ai-stack-audit-latest"
osascript -e "display notification \"$(printf '%s' "$status; alerts $alerts; drift $drift" | tr -d '"\\')\" with title \"AI stack monthly check\"" >/dev/null 2>&1 || true
exit 0
