#!/bin/bash
# inventory.sh - names/counts-only inventory of Cohen's AI coding stack. Writes <out>/inventory.json.
#
# Read-only by construction. Allowlisted commands (nothing else is called):
#   jq (keys/length only on settings and MCP configs), grep -o on TOML section headers, find, readlink,
#   test, stat, shasum -a 256 (hash prefix only, never content), du -sk, df -k, plutil -extract Label,
#   uname, date, wc, sort, tr, sed, perl (timeout wrapper), python3 -I (JSON assembly from stdin),
#   <tool> --version for the version table, and `claude mcp list` ONLY with --with-mcp-list.
# Never reads ~/.claude.json (a Read deny rule covers it; respect it). Never prints env values:
#   settings env is read as `jq '.env|keys'`. All output goes through redact.sh.
#
# Why --with-mcp-list is opt-in: `claude mcp list` health-checks every server, which launches the
#   unpinned `npx -y ...@latest` servers (ground rule 8). Turn it on after PLAN B2 pins them.
#
# Usage: inventory.sh [--out DIR] [--no-versions] [--with-mcp-list]
#        inventory.sh --selftest
# Env:   INV_HOME overrides $HOME (selftest only).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDACT="$HERE/redact.sh"
H="${INV_HOME:-$HOME}"
OUT="."
VERSIONS=1
MCPLIST=0

selftest() {
  local t; t="$(mktemp -d)"
  trap 'rm -rf "$t"' RETURN
  local fh="$t/home"; mkdir -p "$fh/.claude/skills" "$fh/.agents/skills/s1" "$fh/.agents/skills/s2" \
    "$fh/.codex" "$fh/.cursor" "$fh/Library/LaunchAgents" "$fh/Projects/r1/.git" "$fh/Projects/r2" \
    "$fh/Library/Application Support/Claude" "$t/out"
  local fake="FAKEVAL""selftest0123456789abcdefXYZ"
  printf '%s\n' "---" "name: s1" "---" > "$fh/.agents/skills/s1/SKILL.md"
  printf '%s\n' "---" "name: s2" "---" > "$fh/.agents/skills/s2/SKILL.md"
  ln -s "$fh/.agents/skills/s1" "$fh/.claude/skills/s1"
  ln -s "$fh/.agents/skills/missing" "$fh/.claude/skills/broken"
  cat > "$fh/.claude/settings.json" <<JSON
{"permissions":{"allow":["a","b"],"ask":["c"],"deny":["d","e","f"],"defaultMode":"auto","additionalDirectories":["/x"]},
 "env":{"FAKE_API_KEY":"$fake","OTHER":"1"},"hooks":{"PreToolUse":[],"SessionStart":[]},
 "enabledPlugins":{"a@b":true,"c@d":false,"e@f":false}}
JSON
  printf '%s\n' 'sandbox_mode = "workspace-write"' 'approval_policy = "on-request"' '[mcp_servers.alpha]' \
    'command = "x"' '[mcp_servers.beta]' "http_headers = { \"x-auth\" = \"$fake\" }" '[projects."/a"]' > "$fh/.codex/config.toml"
  printf '{"mcpServers":{"one":{"env":{"X":"%s"}},"two":{}}}\n' "$fake" > "$fh/.cursor/mcp.json"
  printf '{"mcpServers":{"d1":{}}}\n' > "$fh/Library/Application Support/Claude/claude_desktop_config.json"
  plutil -create xml1 "$fh/Library/LaunchAgents/com.test.a.plist"
  plutil -insert Label -string com.test.a "$fh/Library/LaunchAgents/com.test.a.plist"
  INV_HOME="$fh" "$0" --out "$t/out" --no-versions >/dev/null
  local j="$t/out/inventory.json" rc=0
  check() { local got; got="$(jq -c "$1" "$j")"; if [[ "$got" == "$2" ]]; then echo "ok $1"; else echo "FAIL $1 got=$got want=$2"; rc=1; fi; }
  check '.claude.permissions.allow' '2'
  check '.claude.permissions.ask' '1'
  check '.claude.permissions.deny' '3'
  check '.claude.env_key_names' '["FAKE_API_KEY","OTHER"]'
  check '.claude.hook_events' '["PreToolUse","SessionStart"]'
  check '.claude.enabled_plugins_false' '2'
  check '.codex.mcp_servers' '["alpha","beta"]'
  check '.codex.sandbox_mode' '"workspace-write"'
  check '.cursor.mcp_servers' '["one","two"]'
  check '.claude_desktop.mcp_servers' '["d1"]'
  check '.skills.claude.entries' '2'
  check '.skills.claude.broken_links' '1'
  check '.skills.agents.with_skill_md' '2'
  check '.launch_agents.labels' '["com.test.a"]'
  check '.projects.git_repos' '1'
  check '.claude.mcp_servers' '"not_collected (run with --with-mcp-list)"'
  if grep -q "selftest0123456789" "$j"; then echo "FAIL secret value leaked"; rc=1; else echo "ok no secret value in output"; fi
  [[ $rc -eq 0 ]] && echo "inventory.sh selftest PASS" || echo "inventory.sh selftest FAIL"
  return $rc
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --selftest) selftest; exit $? ;;
    --out) OUT="$2"; shift 2 ;;
    --no-versions) VERSIONS=0; shift ;;
    --with-mcp-list) MCPLIST=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
mkdir -p "$OUT"
TSV="$(mktemp "${TMPDIR:-/tmp}/inv.XXXXXX")"
trap 'rm -f "$TSV"' EXIT

js() { jq -cn --arg v "$1" '$v'; }                 # JSON string
kv() { printf '%s\t%s\n' "$1" "$2" >> "$TSV"; }   # key path, JSON value
lines_to_json() { jq -Rsc 'split("\n")|map(select(length>0))'; }
tmo() { /usr/bin/perl -e 'alarm shift; exec @ARGV' "$@"; }

# ---- run
kv run.date_local "$(js "$(date '+%Y-%m-%d %H:%M %Z')")"
kv run.tz "$(js "$(readlink /etc/localtime 2>/dev/null | sed 's#.*/zoneinfo/##')")"
kv run.host_os "$(js "$(uname -sr)")"
read -r _ blocks _ avail cap _ < <(df -k / | tail -1)
kv run.disk_free_gb "$(( avail / 1024 / 1024 ))"
kv run.disk_used_pct "${cap%\%}"

# ---- versions
if [[ $VERSIONS -eq 1 ]]; then
  ver() { local name="$1"; shift
    if command -v "$1" >/dev/null 2>&1; then
      local v; v="$( { tmo 15 "$@" 2>&1 || true; } | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?([.-][0-9A-Za-z]+)?' | head -1 || true)"
      kv "versions.$name" "$(js "${v:-unknown}")"
    else kv "versions.$name" '"missing"'; fi; }
  ver claude_code claude --version; ver codex_cli codex --version; ver cursor_cli cursor-agent --version
  ver xcode xcodebuild -version; ver swift swift --version; ver python3 python3 --version
  ver bun bun --version; ver uv uv --version; ver gh gh --version; ver gitleaks gitleaks version
  ver jq jq --version; ver ripgrep rg --version; ver node node --version; ver npm npm --version
  ver pnpm pnpm --version; ver wrangler wrangler --version; ver xcodegen xcodegen --version
  ver swiftlint swiftlint version; ver swiftformat swiftformat --version; ver git git --version
  ver trufflehog trufflehog --version; ver osv_scanner osv-scanner --version; ver ccusage ccusage --version
  HOMEBREW_NO_AUTO_UPDATE=1 ver homebrew brew --version
fi

# ---- Claude settings (counts + key names only)
S="$H/.claude/settings.json"
if [[ -f "$S" ]]; then
  for k in allow ask deny; do kv "claude.permissions.$k" "$(jq "(.permissions.$k // []) | length" "$S")"; done
  kv claude.permissions.default_mode "$(jq -c '.permissions.defaultMode // null' "$S")"
  kv claude.permissions.additional_directories "$(jq '(.permissions.additionalDirectories // []) | length' "$S")"
  kv claude.env_key_names "$(jq -c '(.env // {}) | keys' "$S")"
  kv claude.hook_events "$(jq -c '(.hooks // {}) | keys' "$S")"
  kv claude.sandbox_key "$(jq 'has("sandbox")' "$S")"
  kv claude.enabled_plugins_true "$(jq '[(.enabledPlugins // {})[] | select(. == true)] | length' "$S")"
  kv claude.enabled_plugins_false "$(jq '[(.enabledPlugins // {})[] | select(. == false)] | length' "$S")"
fi
if [[ $MCPLIST -eq 1 ]] && command -v claude >/dev/null; then
  kv claude.mcp_servers "$(tmo 120 claude mcp list 2>/dev/null | "$REDACT" | grep -E '^[^ ].*: ' \
    | sed -E 's/^([^:]+):.*(Connected|Failed|Needs authentication|Pending).*$/\1 [\2]/; s/^([^:[]+):.*/\1/' | lines_to_json)"
else
  kv claude.mcp_servers '"not_collected (run with --with-mcp-list)"'
fi
kv claude.agents "$(find "$H/.claude/agents" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
kv claude.commands "$(find "$H/.claude/commands" -maxdepth 2 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
kv claude.rules "$(find "$H/.claude/rules" -maxdepth 2 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
kv claude.transcripts_jsonl "$(find "$H/.claude/projects" -name '*.jsonl' 2>/dev/null | wc -l | tr -d ' ')"
kv claude.projects_size_mb "$(( $(du -sk "$H/.claude/projects" 2>/dev/null | cut -f1 || echo 0) / 1024 ))"

# ---- Codex (TOML headers and two policy lines only)
C="$H/.codex/config.toml"
if [[ -f "$C" ]]; then
  kv codex.mcp_servers "$(grep -oE '^\[mcp_servers\.[A-Za-z0-9_-]+\]' "$C" | sed -E 's/^\[mcp_servers\.(.*)\]$/\1/' | sort -u | lines_to_json)"
  kv codex.project_trust_entries "$(grep -cE '^\[projects\.' "$C" || true)"
  kv codex.config_lines "$(wc -l < "$C" | tr -d ' ')"
  for k in sandbox_mode approval_policy; do
    v="$(grep -E "^$k[[:space:]]*=" "$C" | head -1 | sed -E 's/^[^=]*=[[:space:]]*"?([A-Za-z-]+)"?.*/\1/' || true)"
    kv "codex.$k" "$(js "${v:-unset}")"
  done
fi
kv codex.sessions_size_mb "$(( $(du -sk "$H/.codex/sessions" 2>/dev/null | cut -f1 || echo 0) / 1024 ))"

# ---- Cursor and Claude desktop (server names only)
[[ -f "$H/.cursor/mcp.json" ]] && kv cursor.mcp_servers "$(jq -c '(.mcpServers // {}) | keys' "$H/.cursor/mcp.json")"
kv cursor.rules_mdc "$(find "$H/.cursor/rules" -maxdepth 1 -name '*.mdc' 2>/dev/null | wc -l | tr -d ' ')"
D="$H/Library/Application Support/Claude/claude_desktop_config.json"
[[ -f "$D" ]] && kv claude_desktop.mcp_servers "$(jq -c '(.mcpServers // {}) | keys' "$D")"

# ---- skills: entries, symlinks, broken links, SKILL.md present
for pair in agents:.agents/skills claude:.claude/skills cursor:.cursor/skills codex:.codex/skills grok:.grok/skills; do
  name="${pair%%:*}"; dir="$H/${pair#*:}"
  [[ -d "$dir" ]] || { kv "skills.$name" '"absent"'; continue; }
  entries=0; links=0; broken=0; withmd=0
  while IFS= read -r -d '' e; do
    entries=$((entries+1))
    [[ -L "$e" ]] && links=$((links+1))
    [[ -L "$e" && ! -e "$e" ]] && broken=$((broken+1))
    [[ -f "$e/SKILL.md" ]] && withmd=$((withmd+1))
  done < <(find "$dir" -mindepth 1 -maxdepth 1 ! -name '.*' -print0)
  kv "skills.$name.entries" "$entries"; kv "skills.$name.symlinks" "$links"
  kv "skills.$name.broken_links" "$broken"; kv "skills.$name.with_skill_md" "$withmd"
done

# ---- LaunchAgents (labels only)
labels="$(for p in "$H"/Library/LaunchAgents/*.plist; do [[ -f "$p" ]] || continue; plutil -extract Label raw -o - "$p" 2>/dev/null || basename "$p" .plist; echo; done | sort -u)"
kv launch_agents.labels "$(printf '%s\n' "$labels" | lines_to_json)"
kv launch_agents.count "$(printf '%s\n' "$labels" | grep -c . || true)"

# ---- projects
kv projects.top_level "$(find "$H/Projects" -mindepth 1 -maxdepth 1 ! -name '.*' 2>/dev/null | wc -l | tr -d ' ')"
kv projects.git_repos "$(find "$H/Projects" -maxdepth 3 -name .git -prune 2>/dev/null | wc -l | tr -d ' ')"

# ---- backup copies in agent config dirs (count only) and config hash prefixes (never content)
kv configs.bak_files "$(find "$H/.claude" "$H/.codex" "$H/.cursor" "$H/.agents" -maxdepth 2 -name '*.bak*' 2>/dev/null | wc -l | tr -d ' ')"
for f in .claude/settings.json .claude/CLAUDE.md .agents/AGENTS.md .agents/CONTEXT.md .agents/mcp.env \
         .codex/config.toml .codex/hooks.json .cursor/mcp.json .cursor/hooks.json .zshrc .zshenv .zprofile .gitconfig \
         "Library/Application Support/Claude/claude_desktop_config.json" .claude/hooks/lint-on-edit.py .claude/hooks/load-design-env.sh; do
  p="$H/$f"; [[ -f "$p" ]] || continue
  kv "configs.sha256_prefix.$(printf '%s' "$f" | tr ' .' '__')" "$(js "$(shasum -a 256 "$p" | cut -c1-16)")"
done

python3 -I -c '
import json, sys
d = {}
for line in sys.stdin:
    k, v = line.rstrip("\n").split("\t", 1)
    cur = d; parts = k.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = json.loads(v)
print(json.dumps(d, indent=1, sort_keys=True))' < "$TSV" | "$REDACT" > "$OUT/inventory.json"
jq -c '{permissions: .claude.permissions, skills: (.skills|map_values(if type=="object" then .entries else . end)), launch_agents: .launch_agents.count, repos: .projects.git_repos, disk_free_gb: .run.disk_free_gb}' "$OUT/inventory.json" | "$REDACT"
