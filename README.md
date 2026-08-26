# cococool/agent-skills

Cohen's personal agent skills — source-managed via the [skills CLI](https://github.com/vercel-labs/skills).

## Install

```bash
npx skills add cococool13/agent-skills --all -g -y
```

## Update

Weekly via LaunchAgent `com.cococool.skills-update`, or manually:

```bash
bash ~/.agents/skills/maintain-skill-library/scripts/update-skills.sh
```

## Layout

```
skills/<name>/SKILL.md   # one folder per skill
```

## Not in this repo

| Skill | Why |
| --- | --- |
| `impeccable` | Local design system with heavy scripts; managed in-place |
| `qcc1-agentic-trading` | Project-local stub → `Projects/Agentic Account` |
| `ego-browser` | Upstream `citrolabs/ego-lite`; local overlays in `~/.agents/skill-overlays/` |
| `impeccable` | Upstream `pbakaus/impeccable` (auto-updates via lock file) |

Upstream skills (emilkowalski, vercel-labs, uizze, etc.) install separately via `npx skills add`.
