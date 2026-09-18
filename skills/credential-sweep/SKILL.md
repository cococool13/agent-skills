---
name: credential-sweep
description: "Use when scanning for exposed secrets or handling credential-bearing local files."

---

# Credential Sweep

Secrets keep getting mis-handled across file, Notes, and Mac work — a
`Passwords.csv` was auto-sorted into a *School* folder by extension match, a
GitHub PAT was left sitting in `.zshrc`, and Bitwarden/Apple-Passwords exports
get re-flagged every cleanup with no standard handling. This skill is the single
source of truth for how to treat anything that looks like a secret.

## Golden rule
**Never sort a credential file by its extension.** A `.csv` of passwords is NOT
a spreadsheet; a `.txt` of recovery codes is NOT a note. Detection by *content
and name pattern* always overrides extension-based routing.

## What counts as a secret (detect these)
**By filename:** `*password*`, `*passwords*`, `*secret*`, `*credential*`,
`*bitwarden*`, `*1password*`, `*lastpass*`, `*keepass*`, `ApplePasswords*`,
`*recovery*code*`, `*backup*code*`, `*seed*phrase*`, `*mnemonic*`,
`id_rsa*`, `id_ed25519*`, `*.pem`, `*.key`, `*.p12`, `*.keychain*`,
`*.env`, `.env.*`, `*service-account*.json`, `*credentials.json`.
**By content (scan text/csv/md/json/dotfiles):** lines matching
`(api[_-]?key|secret|token|password|passwd|pwd|bearer)\s*[:=]`,
GitHub PATs (`ghp_`, `github_pat_`), AWS keys (`AKIA[0-9A-Z]{16}`),
Slack tokens (`xox[baprs]-`), private-key headers
(`-----BEGIN .* PRIVATE KEY-----`), JWTs, and Supabase/Firebase URLs with keys.

## Handling procedure
Read-only audits report locations for review; they do not move files. Respect the
global ban on opening secret or environment files. Use filename evidence or an
authorized scanner that reports only filenames and rule identifiers. Do not copy
secret values into backups, reports, or quarantine notes.

1. **Quarantine only within an authorized organization task.** Move confirmed
   credential exports only when that move is authorized, into a single
   `_secrets-review/` folder at the root of the area being organized. Do NOT
   place it in School/Personal/Career/Media or any topical bucket.
2. **Never delete** unless the user explicitly says so per-file (they have before:
   "delete the apple passwords and bitwarden csv, keep the github codes"). Honor
   that exact granularity. Default action for a scan is report only; an authorized organization task may quarantine exports.
3. **Never print secret values** in chat, logs, or the changelog. Reference files
   by name and the *type* of secret only (e.g. "Bitwarden export — 1 file").
4. **Dotfile tokens are live exposures — escalate.** If a token/PAT/key is found
   in `.zshrc`, `.bashrc`, `.netrc`, shell history, or committed code, flag it
   loudly: state it's exposed, recommend rotating/revoking it at the provider,
   and identify the affected file without reading or copying the value. Credential
   changes require explicit authorization; do not move live configuration files. Remind that rotating locally is not enough — revoke server-side.

## Reporting
End every run with a short secrets section in the changelog/summary:
- Count and type of secrets found (no values).
- Where each was quarantined.
- Any live exposures (dotfile tokens) and the recommended revoke/rotate action.
- Anything the user must decide (keep vs delete) — list per file, await instruction.

## Integration with other skills
This is designed to run *inside* `organize-mac-files`. When it sorts files and hits
a detected secret, hand off to this procedure instead of the normal taxonomy.

`organize-google-drive` and `declutter-apps` used to be hand-off callers; both were
removed on 2026-07-31. This skill still triggers on its own, and the rules below
apply regardless of which skill is driving — including when the user asks about
Drive, Notes, or Mail with no organizing skill in play. **Never fall back to
extension-based sorting for a suspected secret.**

For a standalone scan, use the area Cohen named or the active project. Do not
expand a project scan into Downloads, home, or dotfiles without an explicit request.

## Guardrails (per global agent rules)
- Never permanently delete — quarantine to `_secrets-review/` (or `_trash/` if
  the user approves), never `rm`.
- Never echo secret values.
- Ask before any bulk move touching 20+ files.
