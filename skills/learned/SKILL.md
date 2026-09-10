---
name: learned
description: "Use when environment gotchas, hosting map, or design/skill routing are needed beyond the project context."

---

# Learned

Always-on policy: `~/.agents/AGENTS.md`. Durable environment facts: `~/.agents/CONTEXT.md` (also summarized below). Project files still win inside a repo.

## Quick facts

- Prefer naming `YYYY-MM-DD-descriptive-name.ext` and end file ops with a changelog.
- Prefer `.xlsx` with formulas over `.csv`.
- Xcode 27 RC at `/Applications/Xcode.app`. They Hold ships with `archive-upload.sh` + `asc.py`; Unboxed/Lumen with `package.sh`. Never called Latch in UI.
- Ego Lite wrapper: `"$HOME/.local/bin/ego-browser"`. Do not edit `ego lite.app`.

## Design / craft routing

| Intent | Skill |
| --- | --- |
| UI research / real app refs | `refero-design` (Mobbin MCP ok as a tool under Refero) |
| New marketing / landing page | `landing-page-design` → then `impeccable` |
| Build/extend site from a spec | `premium-web-build` |
| Polish after direction is set | `impeccable` |
| Emil Kowalski polish pass | `emil-design-eng` (not a full redesign) |
| Motion implement / audit / debug | `motion` |
| Pre-ship de-AI / production pass | `de-ai-production-pass` |
| Score generic UI | `ui-slop-score` (manual; often after `impeccable`) |
| Tests / coverage (Py/JS/TS) | `test-coverage` |
| Prose AI-tell cleanup | `unslop` (user-invoked) |
| Deploy | project `CLAUDE.md` → `deploy-cloudflare` |
| `/ship` | `ship` — commit, push, deploy current repo only |
| React/Next performance | `vercel-react-best-practices` (authorship, not hosting) |
| Local files | `organize-mac-files` |
| Secrets | `credential-sweep` |
| `/ponytail` | `ponytail` (audit/review are routes inside it) |

Parked skills (Orca, Diffusion Studio, grill stubs, and others) live in `~/.agents/parked-not-for-cursor`. Restore only when the matching tools are installed.

After `npx skills update`, run:
`python3 ~/.agents/skills/maintain-skill-library/scripts/post-update-patches.py`
and
`python3 ~/.agents/skills/maintain-skill-library/scripts/prune-cursor-scan-paths.py`.

Dated prompt cruft → `prompt-audit` (do not install `anthropics/skills@claude-api`).

## Keep this current

When a new durable preference or recurring gotcha shows up across sessions, add it to `~/.agents/CONTEXT.md` (environment) or `~/.agents/AGENTS.md` (always-on policy).
