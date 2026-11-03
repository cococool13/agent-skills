# stackctl

One manifest (`stack.yaml`) renders rules, skills, MCP servers, hooks and permission intents for Claude Code, Codex, Cursor, Claude desktop and Grok. Nothing here is installed. The prototype `stackctl.py` runs `--selftest` on a synthetic fixture and `check` read-only against live files; `render` only works with `--dry-run`.

## Files

| File | What |
|---|---|
| `stack.yaml` | Manifest. Names, pins, env-var names, per-client flags. No secret values. Pre-filled from the 2026-10-19 state. Machine-specific and git-ignored: it maps one machine's permission setup, so it stays out of this public repo. Pass your own with `--manifest`. |
| `stack.schema.json` | JSON Schema 2020-12. Trust level 1: env names must match `^[A-Z][A-Z0-9_]{2,63}$`, URLs must be https with no query string, strings that look like credentials are rejected, stdio servers need a pin. |
| `stackctl.py` | Prototype. Python 3.11+ stdlib only (`tomllib` for Codex and Grok). |

## Commands

```
stackctl check   [--manifest stack.yaml] [--home ~] [--state ~/.agents/.stackctl-state.json] [--quiet]
stackctl render  --dry-run                   # prints projected diffs; writes nothing
stackctl render                              # production only: backs up, merges, writes, records hashes
stackctl diff                                # production alias of render --dry-run with full file diffs on projections
stackctl import                              # production: pull a live entry into the manifest (names only; refuses values)
stackctl --selftest
```

Exit codes: `0` in sync, `1` drift, `2` manifest invalid or usage error.

## What `render` would write, per client

| Client | File | Managed region | Merge strategy |
|---|---|---|---|
| Claude Code | `~/.claude.json` | `mcpServers` user scope, only the names listed in the manifest | JSON deep-merge on managed keys. Every other key (`projects`, `oauthAccount`, caches, `numStartups`, 55+ keys) is copied through untouched. An unmanaged server in `mcpServers` is left alone and reported as `D-UNMANAGED`. |
| Claude Code | `~/.claude/settings.json` | `permissions.allow/ask/deny` entries that stackctl generated (tracked in state), `hooks.*` entries whose command path is a manifest hook | Set-merge: add missing generated rules, remove only rules stackctl added earlier (state file), never remove a hand-written `deny` or `ask`. |
| Codex | `~/.codex/config.toml` | `[mcp_servers.<name>]` tables for manifest names, plus `disabled_tools` and `tools.<t>.approval_mode` | TOML section replacement: each managed table is written between `# BEGIN stackctl <name>` and `# END stackctl <name>` markers. Everything outside markers is byte-preserved. `approval_policy` and `sandbox_mode` are never written (reported only). |
| Codex | `~/.codex/hooks.json` | hook entries whose command path is a manifest hook | JSON array merge keyed by command path. |
| Cursor | `~/.cursor/mcp.json` | `mcpServers` names in the manifest | JSON deep-merge on managed keys. Headers are rendered as `Bearer ${env:NAME}`. |
| Cursor | `~/.cursor/rules/<fragment>.mdc` | files generated from `rules/fragments` | Whole-file replace, with `# managed by stackctl` on line 1 of the body. A `.mdc` without the marker is never touched. |
| Cursor | `~/.cursor/hooks.json` | same as Codex | JSON merge keyed by command. |
| Claude desktop | `claude_desktop_config.json` | `mcpServers` names in the manifest | JSON deep-merge on managed keys; `preferences` and `coworkUserFilesPath` untouched. http servers render as the `mcp-remote-bearer` stdio bridge, because the desktop app only launches stdio. |
| Grok | `~/.grok/config.toml` | `[mcp_servers.<name>]` override tables only | TOML section replacement with markers. `[compat.cursor]` is reported, not written. |
| Skills | `~/.claude/skills`, `~/.cursor/skills`, `~/.codex/skills` | symlinks into `skills.canonical` | Same algorithm as `sync-claude-skills.py` today, but `skip`, `skip_prefixes`, `extra` and `app_owned` come from the manifest instead of Python constants. Real directories are never removed, only reported. |
| Rules | `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.cursor/AGENTS.md`, `~/.grok/AGENTS.md` | the import line or the symlink | Create if missing; report if a real file sits there. The content of `AGENTS.md` is never generated: it is the source. |

Shared write rules:

1. Dry-run is the default. `render` without `--dry-run` needs `--write`.
2. Before any write: copy to `<file>.bak-stackctl-<YYYY-MM-DD>` and verify the copy exists and has the same size.
3. Idempotent: a second `render --write` produces zero diff. The selftest will assert this once write mode exists.
4. Refuse to write when the live managed region contains a literal credential that the rendered output would drop (for example the treg `Authorization` value in `~/.claude.json`). Message: "move the value to `<env file>` as `TREG_MCP_TOKEN`, then re-run". The value itself is never printed.
5. Refuse to write `~/.claude.json` while a `claude` process is running, and `config.toml` while `codex` is running: both hosts rewrite their files and would overwrite the change.
6. After writing, record `sha256` of each written file in `~/.agents/.stackctl-state.json`. `check` compares the live hash with the recorded one: a mismatch with no manifest drift is `D-OOB` (edited out of band: `claude mcp add`, `codex mcp add`, the desktop app, or by hand). The answer is `stackctl import` (adopt) or `stackctl render --write` (revert), both approval-gated.

## Secrets

- The manifest holds env-var NAMES only. The schema rejects values that look like tokens, and `validate` in the prototype does the same (see `SECRET_RE`).
- Values live in `~/.agents/mcp.env` (mode `600`) or the Keychain (`security add-generic-password -s stackctl.<NAME>`). Only the stdio wrappers resolve them, one variable each (the `gemini-mcp` pattern), never `set -a; source` of the whole file.
- Clients that read env refs do so natively: Claude Code `${NAME}` in `headers`, Cursor `${env:NAME}`, Codex `bearer_token_env_var`/`env_http_headers`. The desktop app gets a bridge.
- `check` output and `render --dry-run` diffs are built from projections (names, transport, URL without query, env key names, header key names, whether a header is a literal). The selftest asserts a fake token planted in the fixture never reaches stdout.
- gitleaks runs as a pre-commit hook on the manifest repo; the repo `.gitignore` excludes `mcp.env`, `*.bak*`, `.skill-lock.json`.

## Where the manifest lives

Proposed: a new private repo `~/Projects/Agent Stack` containing `stack.yaml`, `stack.schema.json`, `stackctl/`, `rules/` (Cursor fragments) and the hook sources moved out of `Agent Skills/maintain-skill-library/scripts/hooks`. `~/.agents/stack.yaml` is a symlink into it, matching how `~/.codex/AGENTS.md` already links into `~/.agents`. See `workstreams/O.md` for the comparison with making `~/.agents` the repo.

## Drift codes

`D-PIN`, `D-POLICY`, `D-SECRET-INLINE`, `D-SECRET-SCOPE`, `D-MISSING`, `D-UNMANAGED`, `D-TRANSPORT`, `D-COMMAND`, `D-ARGS`, `D-URL`, `D-ENV`, `D-TOOLGATE`, `D-DISABLED`, `D-OOB`, `D-HOOK`, `D-SKILL`, `D-RULES`, `D-FILE`.

## Running it during the audit

```
python3 -I stackctl.py --selftest
python3 -I stackctl.py check | sed -E 's/(key|token|secret|bearer|authorization)[=: ]+[^ "]*/\1=<redacted>/Ig'
python3 -I stackctl.py render --dry-run | grep '^## '
```

On 2026-10-19 the selftest passed (14 fixture drifts, no secret text) and the live check reported 18 drifts, listed in `workstreams/O.drifts.csv`.

## Not in the prototype

Write mode, TOML marker rendering, `.mdc` rendering, `import`, the state file writer, PyYAML/jsonschema validation (replace the subset loader and `validate()` with pinned `pyyaml` and `jsonschema` when installing), the `claude mcp list` connector roster check, and the SessionStart warn-only hook (`stackctl check --quiet`, budget 200 ms: it reads five files and no network).
