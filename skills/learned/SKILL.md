---
name: learned
description: "Use when environment gotchas, hosting map, or design/skill routing are needed beyond the project context."

---

# Learned

Always-on policy: `~/.agents/AGENTS.md`. Durable environment facts: `~/.agents/CONTEXT.md`. Project files still win inside a repo.

After install, put **your** machine/hosting notes in `~/.agents/CONTEXT.md`. The quick facts below are the author's examples so his agents keep working; replace them with yours if this is your machine.

## Quick facts (author examples — swap for your setup)

- Prefer naming `YYYY-MM-DD-descriptive-name.ext` and end file ops with a changelog.
- Prefer `.xlsx` with formulas over `.csv`.
- Xcode at `/Applications/Xcode.app` when doing iOS. Prefer project ship scripts over ad-hoc clicks.
- Ego Lite wrapper when installed: `"$HOME/.local/bin/ego-browser"`.

## Design / craft routing

| Intent | Skill |
| --- | --- |
| UI research / real app refs | `refero-design` (Mobbin MCP ok as a tool under Refero) |
| New marketing / landing page | `landing-page-design` → then `impeccable` if installed |
| Build/extend site from a spec | `premium-web-build` |
| Polish after direction is set | `impeccable` |
| Emil Kowalski polish pass | `emil-design-eng` (not a full redesign) |
| Motion implement / audit / debug | `motion` |
| Pre-ship de-AI / production pass | `de-ai-production-pass` |
| Tests / coverage (Py/JS/TS) | `test-coverage` |
| Prose AI-tell cleanup | `unslop` (user-invoked) |
| Deploy | project `CLAUDE.md` → `deploy-cloudflare` |
| `/ship` | `ship` — commit, push, deploy current repo only |
| React/Next performance | `vercel-react-best-practices` (authorship, not hosting) |
| Local files | `organize-mac-files` |
| Secrets | `credential-sweep` |
| `/ponytail` | `ponytail` |

Parked skills live in `~/.agents/parked-not-for-cursor` when you use that layout. Restore only when the matching tools are installed.

After `npx skills update`, if you use this repo's maintainer scripts, run:
`python3 ~/.agents/skills/maintain-skill-library/scripts/post-update-patches.py`
and
`python3 ~/.agents/skills/maintain-skill-library/scripts/prune-cursor-scan-paths.py`.

Dated prompt cruft → `prompt-audit`.

## Keep this current

When a new durable preference or recurring gotcha shows up across sessions, add it to `~/.agents/CONTEXT.md` (environment) or `~/.agents/AGENTS.md` (always-on policy).
