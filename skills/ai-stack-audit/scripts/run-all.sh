#!/bin/bash
# run-all.sh - run the free, script-only parts of the AI stack audit into one run dir. Read-only.
#
# Order: redact selftest -> inventory -> gh-fleet -> stackctl check -> MCP hashes + diff -> mine
#        -> deps (OSV) -> live (only with --urls) -> report diff vs the previous run.
# No `claude -p`, no `codex exec`, no MCP calls, no npx, no installs, no mutations.
#
# Write guard: TMPDIR points inside the run dir; a stamp file is created first; at the end
# `find <watched> -newer <stamp>` lists every file changed anywhere in ~/.claude ~/.codex ~/.cursor
# ~/.agents ~/Library/LaunchAgents and the top of ~/Projects. Changes under known live-session paths
# (transcripts, todos, shell snapshots, Codex sessions/logs) are listed as "noise" because other
# open sessions write there. Anything else is "unexpected" and the run exits 3.
#
# Allowlisted commands: the sibling scripts, ../stackctl/stackctl.py check, gh auth status, find,
# date, mkdir, rmdir, touch (stamp inside run dir only), ls, tee, grep.
#
# Usage: run-all.sh [--run-dir DIR] [--prev DIR] [--urls urls.json] [--no-network] [--skip-gh]
#        run-all.sh --selftest
# Default run dir: ~/Projects/_review/ai-stack-audit-$(date +%F)/script-run
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDACT="$HERE/redact.sh"
STACKCTL="$HERE/../stackctl/stackctl.py"
REVIEW="$HOME/Projects/_review"
RUN=""; PREV=""; URLS=""; NET=1; GH=1
WATCH_DEFAULT=("$HOME/.claude" "$HOME/.codex" "$HOME/.cursor" "$HOME/.agents" "$HOME/Library/LaunchAgents")
NOISE_RE='/\.claude/(backups|projects|todos|shell-snapshots|statsig|session-env|sessions|debug|telemetry|file-history|tasks|paste-cache|ide|plans|history\.jsonl|\.credentials|cache)|/\.codex/(sessions|log|logs|shell_snapshots|memories|memories_v2|cache|tmp|\.codex-global-state\.json|.*\.sqlite)|/\.cursor/(projects|ai-tracking|chats|extensions|cli-config\.json|statsig)|/\.codex/plugins/cache/[^/]+/[^/]+/\.codex-remote-plugin-install\.json|/\.agents/\.stackctl-state'

# write_check STAMP ROOT...  -> prints noise/unexpected lists, returns 3 if unexpected
write_check() {
  local stamp="$1"; shift
  local changed; changed="$(find "$@" -newer "$stamp" -type f 2>/dev/null | sort || true)"
  local noise unexpected
  noise="$(printf '%s\n' "$changed" | grep -E "$NOISE_RE" | grep . || true)"
  unexpected="$(printf '%s\n' "$changed" | grep -vE "$NOISE_RE" | grep . || true)"
  echo "write-check: $(printf '%s\n' "$noise" | grep -c . || true) noise, $(printf '%s\n' "$unexpected" | grep -c . || true) unexpected"
  [[ -n "$noise" ]] && printf '  noise: %s\n' $(printf '%s\n' "$noise" | sed -E 's#^(.*/\.(claude|codex|cursor|agents)/[^/]+).*#\1#' | sort | uniq -c | awk '{print $2"("$1")"}') || true
  if [[ -n "$unexpected" ]]; then printf '  UNEXPECTED: %s\n' $unexpected; return 3; fi
  return 0
}

selftest() {
  local rc=0 t; t="$(mktemp -d)"
  trap 'rm -rf "$t"' RETURN
  for s in "redact.sh --selftest" "inventory.sh --selftest" "gh-fleet.sh --selftest"; do
    if bash "$HERE/${s%% *}" "${s#* }" >"$t/o" 2>&1; then echo "ok ${s%% *}"; else echo "FAIL ${s%% *}"; tail -5 "$t/o"; rc=1; fi
  done
  for s in mcp-hashes.py report.py mine.py deps.py live.py; do
    if python3 -I "$HERE/$s" --selftest >"$t/o" 2>&1; then echo "ok $s"; else echo "FAIL $s"; tail -5 "$t/o"; rc=1; fi
  done
  if bash "$HERE/mac-dist.sh" --selftest >"$t/o" 2>&1; then echo "ok mac-dist.sh"; else echo "WARN mac-dist.sh (missing tool?)"; fi
  if python3 -I "$STACKCTL" --selftest >"$t/o" 2>&1; then echo "ok stackctl.py"; else echo "FAIL stackctl.py"; rc=1; fi
  # write_check catches a write outside the run dir and ignores noise paths
  mkdir -p "$t/w/.claude/projects/x" "$t/w/.agents"
  touch "$t/stamp"; sleep 1
  touch "$t/w/.claude/projects/x/a.jsonl"
  if write_check "$t/stamp" "$t/w" >/dev/null; then echo "ok write_check ignores noise"; else echo "FAIL write_check noise"; rc=1; fi
  touch "$t/w/.agents/AGENTS.md"
  if write_check "$t/stamp" "$t/w" >/dev/null; then echo "FAIL write_check missed a write"; rc=1; else echo "ok write_check flags an unexpected write"; fi
  # no forbidden commands in any script body (headless model runs, installs, mutations)
  local forb='(claude -p|codex exec|npx |bunx |uvx |brew (install|upgrade)|npm (install|i )|pip install|launchctl (load|bootstrap)|wrangler deploy|git (push|commit|checkout))'
  local hits
  hits="$( { grep -nE "^[^#]*\\b$forb" "$HERE"/*.sh | grep -v 'local forb=' || true
             grep -nE 'subprocess\.(run|Popen|call|check_output)\(\["(claude|codex|npx|bunx|uvx|brew|npm|pip|launchctl|wrangler)"' "$HERE"/*.py || true
             grep -nE 'subprocess\.[a-z_]+\(\["git", "-C", [a-z]+, "(push|commit|checkout|reset|fetch)' "$HERE"/*.py || true; } )"
  if [[ -n "$hits" ]]; then echo "FAIL forbidden command in a script body:"; echo "$hits"; rc=1
  else echo "ok no forbidden commands in script bodies (shell lines + python subprocess calls)"; fi
  [[ $rc -eq 0 ]] && echo "run-all.sh selftest PASS" || echo "run-all.sh selftest FAIL"
  return $rc
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --selftest) selftest; exit $? ;;
    --run-dir) RUN="$2"; shift 2 ;;
    --prev) PREV="$2"; shift 2 ;;
    --urls) URLS="$2"; shift 2 ;;
    --no-network) NET=0; shift ;;
    --skip-gh) GH=0; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
RUN="${RUN:-$REVIEW/ai-stack-audit-$(date +%F)/script-run}"
mkdir -p "$RUN/.tmp"
export TMPDIR="$RUN/.tmp"
STAMP="$RUN/.stamp"; touch "$STAMP"; sleep 1
LOG="$RUN/run-all.log"; : > "$LOG"
if [[ -z "$PREV" ]]; then  # newest earlier run that has a baseline-mcp-tools.json
  PREV="$(ls -d "$REVIEW"/ai-stack-audit-20*/ 2>/dev/null | sed 's#/$##' | grep -v "^$(dirname "$RUN")$" | grep -v "^$RUN$" | sort | tail -1 || true)"
fi

step() { local name="$1"; shift; echo "== $name" | tee -a "$LOG"
  if "$@" 2>&1 | "$REDACT" >> "$LOG"; then echo "   ok" | tee -a "$LOG"; else echo "   exit ${PIPESTATUS[0]}" | tee -a "$LOG"; fi; }

step redact-selftest bash "$HERE/redact.sh" --selftest
step inventory bash "$HERE/inventory.sh" --out "$RUN"
if [[ $GH -eq 1 ]] && gh auth status >/dev/null 2>&1; then step gh-fleet bash "$HERE/gh-fleet.sh" --out "$RUN"; else echo "== gh-fleet skipped" | tee -a "$LOG"; fi
step stackctl-check sh -c "python3 -I '$STACKCTL' check --quiet > '$RUN/stackctl-check.txt' 2>&1; echo drift_exit=\$?"
step mcp-hashes python3 -I "$HERE/mcp-hashes.py" from-transcripts --out "$RUN/baseline-mcp-tools.json"
if [[ -n "$PREV" && -f "$PREV/baseline-mcp-tools.json" ]]; then
  step mcp-diff sh -c "python3 -I '$HERE/mcp-hashes.py' diff '$PREV/baseline-mcp-tools.json' '$RUN/baseline-mcp-tools.json' --warn-only > '$RUN/mcp-diff.txt'"
fi
step mine python3 -I "$HERE/mine.py" --out "$RUN/mine-output.json"
if [[ $NET -eq 1 ]]; then step deps python3 -I "$HERE/deps.py" scan --out "$RUN/deps"
else step deps python3 -I "$HERE/deps.py" scan --out "$RUN/deps" --no-network; fi
if [[ -n "$URLS" && $NET -eq 1 ]]; then step live python3 -I "$HERE/live.py" batch "$URLS" --out "$RUN/live"; else echo "== live skipped (no --urls or --no-network)" | tee -a "$LOG"; fi
[[ -n "$PREV" ]] && step report-diff sh -c "python3 -I '$HERE/report.py' '$PREV' > '$RUN/prev-summary.md'; echo prev=$PREV"

rmdir "$RUN/.tmp" 2>/dev/null || true
echo "== write check" | tee -a "$LOG"
PROJ_TOP=(); for d in "$HOME"/Projects/*/; do [[ "$d" == *"/_review/" ]] || PROJ_TOP+=("$d"); done
set +e
write_check "$STAMP" "${WATCH_DEFAULT[@]}" | tee -a "$LOG"; wc1=${PIPESTATUS[0]}
# top of each project (depth 2), cheap and catches stray output files
changed_proj="$(find "${PROJ_TOP[@]}" -maxdepth 2 -newer "$STAMP" -type f 2>/dev/null | grep -vE '/(\.git|node_modules|\.build|DerivedData)/' || true)"
set -e
if [[ -n "$changed_proj" ]]; then echo "  projects changed during run (check whether another session did it):"; printf '    %s\n' $changed_proj; fi | tee -a "$LOG"
echo "run dir: $RUN"
exit "$wc1"
