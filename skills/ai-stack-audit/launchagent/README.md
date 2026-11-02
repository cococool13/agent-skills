# Monthly script-only check and config-drift hook (PLAN B13 proposal)

Nothing here is installed. Run these commands only after Cohen approves B13. All paths assume the skill is installed at `~/.agents/skills/ai-stack-audit` (see `../README.md`).

## Files

| File | What |
|---|---|
| `com.cococool.ai-stack-audit-monthly.plist` | launchd job: every Monday 09:00 local time (this Mac is America/New_York) |
| `monthly.sh` | Exits unless day 1-7 (first Monday). Runs `scripts/run-all.sh` only, writes `~/Projects/_review/ai-stack-audit-YYYY-MM-DD/cron/`, then `SUMMARY.md` + a macOS notification |
| `hooks/config-drift.sh` | Warn-only Claude Code hook: `stackctl check` + background MCP hash diff when a config changes |
| `hooks/claude-settings-hooks.json` | The hook entries to merge into `~/.claude/settings.json` |

No `claude -p`, no `codex exec`, no Fable, no model tokens on any schedule. The full model-driven audit stays a manual `/ai-stack-audit` run.

## Install the LaunchAgent

```bash
P=~/Library/LaunchAgents/com.cococool.ai-stack-audit-monthly.plist
S=~/.agents/skills/ai-stack-audit/launchagent
test ! -e "$P" || cp "$P" "$P.bak-audit-2026-10-19"
cp "$S/com.cococool.ai-stack-audit-monthly.plist" "$P"
plutil -lint "$P"
launchctl bootstrap "gui/$(id -u)" "$P"
launchctl print "gui/$(id -u)/com.cococool.ai-stack-audit-monthly" | grep -E 'state|run interval|last exit'
AI_AUDIT_FORCE=1 bash "$S/monthly.sh" && cat ~/Projects/_review/ai-stack-audit-$(date +%F)/cron/SUMMARY.md
```
`launchctl kickstart` would run the job but `monthly.sh` exits on days after the 7th; use `AI_AUDIT_FORCE=1` for a manual test.

## Uninstall / rollback

```bash
launchctl bootout "gui/$(id -u)/com.cococool.ai-stack-audit-monthly"
mv ~/Library/LaunchAgents/com.cococool.ai-stack-audit-monthly.plist ~/.Trash/
```
Run outputs under `~/Projects/_review/ai-stack-audit-*/cron/` stay; delete them only with Cohen's OK.

## Summary channel

Proposed: `SUMMARY.md` in the run dir (one paragraph, passed through `redact.sh`) plus `osascript -e 'display notification ...'` with status, open Dependabot alerts and drift count.
Open question: post the paragraph to Reason Network or the Grok Bot webhook instead? Both need a credential at run time (`GROKBOT_WEBHOOK_KEY` is only exported in interactive shells; launchd would need the Keychain fallback) and count as "sending on Cohen's behalf", so they need his explicit choice.

## Config-change trigger

Claude Code 2.1.x (hooks reference, checked 2026-10-19) has:
- `ConfigChange`: fires for `user_settings` (`~/.claude/settings.json`), `project_settings`, `local_settings`, `policy_settings`, `skills`. It can block, and it discards `systemMessage`, so it is used only to refresh state.
- `FileChanged`: fires when a watched file changes, whatever wrote it. No decision control. Shows `systemMessage`. Absolute paths are watched through `watchPaths`, which the SessionStart hook returns for `~/.claude/settings.json`, `~/.claude.json`, `~/.codex/config.toml`, `~/.cursor/mcp.json`.
- `SessionStart`: compares stored hash prefixes, so a change made between sessions (by Codex, Cursor, an app, or by hand) still warns at the next start.

Cost: no `additionalContext`, so zero context tokens. `stackctl check` takes well under a second; the MCP diff runs detached and reports at the next session start.
Limits: only Claude Code sessions run it; Codex and Cursor have no equivalent event wired here. `watchPaths` placement inside `hookSpecificOutput` follows the SessionStart field table; confirm with `claude --debug` after install.

### Install the hook

```bash
SET=~/.claude/settings.json
cp "$SET" "$SET.bak-audit-2026-10-19" && test -s "$SET.bak-audit-2026-10-19"
bash ~/.agents/skills/ai-stack-audit/launchagent/hooks/config-drift.sh --selftest
jq --slurpfile h ~/.agents/skills/ai-stack-audit/launchagent/hooks/claude-settings-hooks.json '
  .hooks.SessionStart = ((.hooks.SessionStart // []) + $h[0].hooks.SessionStart) |
  .hooks.FileChanged  = ((.hooks.FileChanged  // []) + $h[0].hooks.FileChanged)  |
  .hooks.ConfigChange = ((.hooks.ConfigChange // []) + $h[0].hooks.ConfigChange)' "$SET" > "$SET.new" \
  && jq -e '.hooks.FileChanged' "$SET.new" >/dev/null && mv "$SET.new" "$SET"
jq '.hooks | keys' "$SET"
```
Verify: start a new Claude Code session (no warning on the first run), then `touch ~/.cursor/mcp.json` and expect a "Config changed" notice.

### Roll back the hook

```bash
cp ~/.claude/settings.json.bak-audit-2026-10-19 ~/.claude/settings.json
```
State lives in `~/.agents/.ai-stack-audit/`; move it to `~/.Trash/` to reset.
