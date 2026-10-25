---
name: create-hook
description: "Use when creating or repairing lifecycle hooks for Codex, Cursor, Claude Code, or Grok."
---

# Create or repair hooks

Identify the target client, event, scope, and intended behavior from the request.
Inspect its existing hook configuration before editing. Ask only when missing
information changes the behavior. Hook formats differ between clients; changing
the product name in another client's instructions does not convert the format.

## Locations and formats

| Client | User configuration | Project configuration |
| --- | --- | --- |
| Codex | `~/.codex/hooks.json` | `.codex/hooks.json` |
| Cursor | `~/.cursor/hooks.json` | `.cursor/hooks.json` |
| Claude Code | `~/.claude/settings.json` under `hooks` | `.claude/settings.json` under `hooks` |
| Grok | `~/.grok/hooks/*.json` | `.grok/hooks/*.json` |

On Cohen's machine the shared guards are `~/.agents/hooks/deny-env-read.py` and
`guard-shell.py`. `~/.cursor/hooks/` links to them. Grok does not import Cursor
or Claude hooks (`[compat.cursor] hooks` and `[compat.claude] hooks` are false).
Cursor's reply format does not block in Grok, so do not turn those switches on.
Grok runs `~/.grok/hooks/safety.json` against the same scripts. Each other
client keeps its own configuration adapter.

### Codex

Read the current [official hook documentation](https://learn.chatgpt.com/docs/hooks)
before changing version-sensitive behavior. Codex uses PascalCase event names,
matcher groups, and nested handlers:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{"type": "command", "command": "/absolute/path/guard.py", "timeout": 10}]
    }]
  }
}
```

`exec_command` matches `Bash`. Shell arguments arrive under
`tool_input.command`; other local and MCP tools use their own arguments.
Return only supported fields:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Explain why the operation is blocked."
  }
}
```

Codex currently rejects `permissionDecision: "ask"` and legacy top-level
`decision: "allow"` or `"deny"`. An unsupported output can fail open. A hook
that needs to stop for approval should return a supported denial with an
actionable reason; do not claim it can open an approval dialog.

Hooks are enabled by default. Review new or changed definitions using `/hooks`
in the CLI or the desktop hook settings. Verify trust rather than bypassing it.
Plugin hooks must use this same format; Claude UI-module files containing
`modules` are not Codex lifecycle hooks. Put a Codex compatibility manifest in
the user-owned plugin source when the plugin needs a different hook entrypoint.

### Cursor and Grok's Cursor compatibility

Read [Cursor's hook documentation](https://cursor.com/docs/hooks). Cursor uses
schema version 1 and camelCase events:

```json
{
  "version": 1,
  "hooks": {
    "beforeShellExecution": [{"command": "./hooks/guard.py", "timeout": 10}]
  }
}
```

User-hook commands run relative to `~/.cursor/`; project-hook commands run
relative to the project root. Shell input has a top-level `command`. A gating
hook returns `permission: "allow"`, `"deny"`, or `"ask"`, with optional
`user_message` and `agent_message`. Matchers use JavaScript regular expressions.
Use `failClosed` only where the required failure policy calls for it.

### Claude Code

Read [Claude Code's hook reference](https://code.claude.com/docs/en/hooks).
Preserve existing settings outside `hooks`. Claude uses PascalCase event names
and nested matcher groups similar to Codex, but supports
`hookSpecificOutput.permissionDecision: "ask"`. Use the target client's
documented output contract rather than relying on that similarity.

## Verify the repair

1. Check parsing, executable permissions, interpreter availability, paths,
   event names, matchers, and trust status.
2. Exercise the actual scripts with synthetic input for an allowed action,
   a denied action, and a relevant edge case. Do not read real secrets or run
   destructive operations to test protection.
3. Trigger a harmless real event in the target client and confirm the hook
   fired. Running the script directly does not establish runtime loading.
4. Check the client's hook result for parse errors and unsupported fields.
5. For a shared script, verify each client's response contract independently.
6. Report changed files, checks, and any runtime or login step left unverified.

Keep repairs in user-owned source. Preserve unrelated hooks and settings, and
leave provider-managed bundles intact. Use fresh sessions when the target
client loads hook definitions only at session start.
