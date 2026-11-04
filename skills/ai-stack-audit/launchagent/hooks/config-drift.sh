#!/bin/bash
# config-drift.sh - warn-only Claude Code hook (PROPOSAL, PLAN B13). Never blocks, never edits configs.
#
# Events:
#   SessionStart  compare sha256 prefixes of the watched configs with the stored set; warn on change;
#                 return watchPaths so FileChanged fires for them during the session; show the last
#                 background MCP hash diff if it found changes.
#   FileChanged   a watched config changed (any writer): run `stackctl check --quiet`, start the MCP
#   ConfigChange  hash diff in the background, store new hashes, warn via systemMessage.
#                 (ConfigChange discards systemMessage, so it only refreshes state; FileChanged warns.)
# Output never includes config content: file names, hash prefixes, drift counts only.
# Zero context cost: uses systemMessage (shown to Cohen), never additionalContext.
#
# Allowlisted: jq, shasum, python3 -I (stackctl.py check, mcp-hashes.py), mkdir/mv/date in the state dir.
# State dir: ~/.agents/.ai-stack-audit/ (hashes, last stackctl result, last MCP diff).
#
# Usage: config-drift.sh < hook-input.json        config-drift.sh --selftest
set -uo pipefail   # no -e: a hook must fail open and quiet

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${AI_AUDIT_ROOT:-$(cd "$HERE/../.." && pwd)}"        # installed skill dir
H="${AI_AUDIT_HOME:-$HOME}"
STATE="${AI_AUDIT_STATE:-$H/.agents/.ai-stack-audit}"
WATCH=("$H/.claude/settings.json" "$H/.claude.json" "$H/.codex/config.toml" "$H/.cursor/mcp.json")

hashes() { for f in "${WATCH[@]}"; do
  if [[ -f "$f" ]]; then printf '%s\t%s\n' "${f/#$H/~}" "$(shasum -a 256 "$f" | cut -c1-16)"; else printf '%s\tabsent\n' "${f/#$H/~}"; fi
done; }
changed_since_store() {  # prints changed names
  [[ -f "$STATE/config-hashes.tsv" ]] || return 0
  diff <(sort "$STATE/config-hashes.tsv") <(hashes | sort) | sed -n 's/^> \([^	]*\).*/\1/p'
}
store() { mkdir -p "$STATE" && hashes > "$STATE/config-hashes.tsv.tmp" && mv "$STATE/config-hashes.tsv.tmp" "$STATE/config-hashes.tsv"; }
watch_json() { printf '%s\n' "${WATCH[@]}" | jq -Rsc 'split("\n")|map(select(length>0))'; }

stackctl_summary() {
  local out rc
  out="$(python3 -I "$ROOT/stackctl/stackctl.py" check --quiet --home "$H" 2>&1)"; rc=$?
  printf '%s\n' "$out" > "$STATE/stackctl-last.txt"
  case $rc in 0) echo "stackctl: in sync" ;; 1) echo "stackctl: drift ($(grep -c . <<<"$out") lines, see $STATE/stackctl-last.txt)" ;; *) echo "stackctl: check failed (exit $rc)" ;; esac
}
mcp_diff_bg() {  # needs the session transcript; runs detached so the hook returns fast
  local tp="$1" latest="$H/Projects/_review/latest/baseline-mcp-tools.json"
  [[ -f "$tp" && -f "$latest" ]] || return 0
  ( python3 -I "$ROOT/scripts/mcp-hashes.py" from-transcripts --root "$(dirname "$tp")" --session "$tp" --out "$STATE/session-mcp.json" >/dev/null 2>&1 \
    && python3 -I "$ROOT/scripts/mcp-hashes.py" diff "$latest" "$STATE/session-mcp.json" --warn-only > "$STATE/mcp-diff.txt" 2>&1 ) </dev/null >/dev/null 2>&1 &
}

main() {
  local in ev fp tp msg ch
  in="$(cat)"; ev="$(jq -r '.hook_event_name // empty' <<<"$in" 2>/dev/null)"
  tp="$(jq -r '.transcript_path // empty' <<<"$in" 2>/dev/null)"
  mkdir -p "$STATE" 2>/dev/null
  case "$ev" in
    SessionStart)
      ch="$(changed_since_store | paste -sd, -)"
      msg=""
      [[ -n "$ch" ]] && msg="AI config changed since last session: $ch. $(stackctl_summary)."
      if [[ -f "$STATE/mcp-diff.txt" ]] && ! grep -q 'no MCP definition changes' "$STATE/mcp-diff.txt"; then
        msg="${msg:+$msg }MCP definitions changed vs last audit: see $STATE/mcp-diff.txt."
      fi
      store
      jq -cn --arg m "$msg" --argjson w "$(watch_json)" \
        '{hookSpecificOutput: {hookEventName: "SessionStart", watchPaths: $w}} + (if $m == "" then {} else {systemMessage: $m} end)'
      ;;
    FileChanged|ConfigChange)
      fp="$(jq -r '.file_path // empty' <<<"$in")"
      msg="Config changed: ${fp/#$H/~}. $(stackctl_summary). MCP hash diff running; result at next session start."
      store; mcp_diff_bg "$tp"
      jq -cn --arg m "$msg" '{systemMessage: $m}'
      ;;
    *) echo '{}' ;;
  esac
  return 0
}

selftest() {
  local t rc=0 o; t="$(mktemp -d)"; trap 'rm -rf "$t"' RETURN
  mkdir -p "$t/h/.claude" "$t/h/.codex" "$t/h/.cursor" "$t/root/stackctl" "$t/root/scripts"
  printf '%s\n' 'import sys' 'print("D-PIN example drift"); sys.exit(1)' > "$t/root/stackctl/stackctl.py"
  echo '{"env":{"K":"v"}}' > "$t/h/.claude/settings.json"; echo '[mcp_servers.a]' > "$t/h/.codex/config.toml"
  export AI_AUDIT_HOME="$t/h" AI_AUDIT_STATE="$t/state" AI_AUDIT_ROOT="$t/root"
  o="$(echo '{"hook_event_name":"SessionStart"}' | bash "$0")"
  jq -e '.hookSpecificOutput.watchPaths|length==4' <<<"$o" >/dev/null && echo "ok SessionStart returns 4 watchPaths" || { echo "FAIL watchPaths: $o"; rc=1; }
  jq -e 'has("systemMessage")|not' <<<"$o" >/dev/null && echo "ok first session is quiet" || { echo "FAIL first session warned"; rc=1; }
  echo '[mcp_servers.b]' >> "$t/h/.codex/config.toml"
  o="$(echo '{"hook_event_name":"SessionStart"}' | bash "$0")"
  grep -q 'config.toml' <<<"$o" && grep -q 'stackctl: drift' <<<"$o" && echo "ok change between sessions warned" || { echo "FAIL no warning: $o"; rc=1; }
  o="$(printf '{"hook_event_name":"FileChanged","file_path":"%s","event":"change"}' "$t/h/.cursor/mcp.json" | bash "$0")"
  jq -e '.systemMessage|test("Config changed")' <<<"$o" >/dev/null && echo "ok FileChanged warns" || { echo "FAIL FileChanged: $o"; rc=1; }
  grep -q '"v"' <<<"$o" && { echo "FAIL config value leaked"; rc=1; } || echo "ok no config values in output"
  o="$(echo 'not json' | bash "$0")"; [[ "$o" == "{}" ]] && echo "ok fails open on bad input" || { echo "FAIL bad input: $o"; rc=1; }
  unset AI_AUDIT_HOME AI_AUDIT_STATE AI_AUDIT_ROOT
  [[ $rc -eq 0 ]] && echo "config-drift.sh selftest PASS" || echo "config-drift.sh selftest FAIL"
  return $rc
}

if [[ "${1:-}" == "--selftest" ]]; then selftest; exit $?; fi
main
