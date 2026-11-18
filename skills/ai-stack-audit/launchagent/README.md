# Config-drift hook (PLAN B13)

The monthly LaunchAgent `com.cococool.ai-stack-audit-monthly` was removed on 2026-11-08. Do not bootstrap it again. The config-drift hook below was not part of that job and is not installed. All paths assume the skill is installed at `~/.agents/skills/ai-stack-audit`.

## Files

| File | What |
|---|---|
| `com.cococool.ai-stack-audit-monthly.plist` | Removed from `~/Library/LaunchAgents`. Do not copy it back. |
| `monthly.sh` | Retired with the LaunchAgent. Do not schedule it. |
| `hooks/config-drift.sh` | Warn-only Claude Code hook: `stackctl check` + background MCP hash diff when a config changes |
| `hooks/claude-settings-hooks.json` | The hook entries to merge into `~/.claude/settings.json` |

No `claude -p`, no `codex exec`, no Fable, no model tokens on any schedule. The full model-driven audit stays a manual `/ai-stack-audit` run.

## Monthly LaunchAgent

Removed. Do not install `com.cococool.ai-stack-audit-monthly.plist` or schedule `monthly.sh`. Past run output under `~/Projects/_review/ai-stack-audit-*/cron/` stays; delete it only with Cohen's OK.

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

Not installed. Do not merge it unless Cohen asks.

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
