---
name: organize-mac-files
description: "Use when the user asks to organize, rename, sort, or safely clean up local Mac files."

---

# Organize Mac Files

The user runs this constantly. The whole point of this skill is to STOP
re-deriving the taxonomy and re-discovering environment limits every session.

## Critical environment facts (read first)
- **The `mcp__workspace__bash` sandbox CANNOT reach the real filesystem**
  (`~/Downloads`, `~/Documents`, etc.). Do real file operations with
  **Desktop Commander** (`mcp__Desktop_Commander__*`) or `osascript`. Pick one
  and stick with it — don't re-probe every run.
- **macOS permissions** block `rm` and empty-dir removal from the VM. Run
  destructive removal on the Mac itself (Desktop Commander / osascript). Empty
  iCloud-synced or VM-mounted dirs may refuse removal — note it, don't loop.
- `Documents` may be an iCloud symlink; if so use `Docs` rather than fighting it.

## The standard taxonomy (do NOT re-invent this)
Within `~/Downloads` (and mirrored when sorting the home folder):
- `School/` — coursework, papers, syllabi. Subfolders: `Spreadsheets/`, `Code/`,
  `Presentations/`. (Course tags seen: ENTR 5500/7500, ECON 3300/4750.)
- `Career/` — resumes, cover letters, CV, brand/portfolio. Subfolders `PDFs/`, `Docs/`.
- `Personal/` — essays, housing, personal docs.
- `Media/` — `Images/`, `Videos/`, `Installers/` (.dmg/.pkg), `Other/`.
- `Data/` — datasets, exports.
- `_inbox/` — docs/PDFs awaiting manual sort (drain rule below).
- `_archive/` — zips, .dmg after install, duplicates. Never delete; archive.
- `_needs-review/` — ambiguous items.
- `_trash/` — staging only; move to macOS Trash, never hard-delete.

Other fixed destinations:
- **All project folders consolidate under `~/Projects/`.**
- **Screenshots → `~/Pictures/Screenshots/`.**

## Naming conventions
- Rename screenshots `YYYY-MM-DD-HH-MM-SS.png`. macOS screenshot names contain a
  **narrow no-break space (U+202F)** before AM/PM — strip it when parsing
  `Screenshot YYYY-MM-DD at H.MM.SS PM.png`.
- General files: `YYYY-MM-DD-descriptive-name.ext` where a date is meaningful.
- On name collisions at the destination, append a `-HHMMSS` timestamp suffix.

## Safety rules (non-negotiable)
- **Never permanently delete.** Move to macOS Trash or `_archive`. Even when the
  user says "delete", route to Trash and say so.
- **Ask before bulk moves of 20+ files or ambiguous categorization.** Trivial
  renames/folder creation need no confirmation.
- **Auto-flag plaintext credential/financial files** anywhere encountered
  (`*.csv` password exports, `ApplePasswords.csv`, `Bitwarden*Export*.csv`,
  `*recovery-codes*`, bank statements). Flag and recommend a password manager;
  do not move them into a synced/shared location.

## Deliverable every run
Write a dated changelog: `~/Downloads/_archive/YYYY-MM-DD-cleanup-changelog.md`
(or `changelog.md` in the organized folder). Report with **counts and specifics**
("Moved 47 files into 6 folders; 3 flagged for review"), a per-destination table,
and the current `_inbox` contents with School/Career/Personal suggestions.

## Weekly Downloads cleanup (scheduled entry point)
A scheduled task runs `~/scripts/cleanup-downloads.sh` weekly. Behavior:
1. If the script is missing, regenerate it from `reference/cleanup-downloads.sh`
   in this skill folder (identical routing — never re-guess the taxonomy).
2. Run it via Desktop Commander/osascript (NOT sandbox bash).
3. It is idempotent: skip files already at destination; safe to re-run.
4. **Drain `_inbox`:** obvious coursework (course codes, "Homework",
   "Case Analysis", academic-paper filenames) auto-routes to `School/`; only
   genuinely ambiguous items stay in `_inbox`. Report any remaining backlog.

## When run on a schedule (no conversation context)
Organize `~/Downloads` per the rules above, write the dated changelog, and finish
with a 3–5 line summary (counts moved, `_inbox` backlog size, anything flagged).

## Credential handling → hand off to `credential-sweep`
The inline "flag credentials" rule above is now owned by the **`credential-sweep`**
skill. When sorting, if a file matches a secret pattern (password CSVs,
Bitwarden/1Password/Apple exports, `*.pem`/`*.key`, recovery codes, tokens),
do NOT route it by extension — hand off to `credential-sweep`: quarantine to
`_secrets-review/`, never echo values, never delete unless told per-file.

## VM delete limit + one paste-ready cleanup command
The execution environment often CANNOT delete originals or remove now-empty
folders (macOS permissions / iCloud sync). Don't hand the user a pile of manual
`rm` steps, and never hand out `sudo rm -rf` (it violates the never-delete rule).
Instead: do the moves you can, then emit a SINGLE reviewed, paste-ready command
that stages leftovers to Trash (not `rm`), e.g.:

```bash
# review the list first; this moves to macOS Trash, nothing is destroyed
for d in "$HOME/Downloads/_empty-stub-1" "$HOME/Downloads/_empty-stub-2"; do
  [ -d "$d" ] && mv "$d" "$HOME/.Trash/"; done
```

State the limit up front, and **verify completion before reporting done** (don't
say "moved" if the original is still there).
