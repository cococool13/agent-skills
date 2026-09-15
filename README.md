# Agent skills

Personal skills I use with coding agents (Cursor, Grok, and friends).

A **skill** is a short markdown recipe. You ask in plain English; the agent loads the matching skill and follows it.

## Install

```bash
npx skills add cococool13/agent-skills --all -g -y
```

Update later: `npx skills update -g -y`

## Skills

### Design

| Skill | What it does |
| --- | --- |
| [`refero-design`](skills/refero-design/SKILL.md) | Research real app screens before inventing UI. |
| [`landing-page-design`](skills/landing-page-design/SKILL.md) | Design or revise a landing / marketing page. |
| [`redesign-existing-projects`](skills/redesign-existing-projects/SKILL.md) | Upgrade an existing site’s look, UX, or quality. |
| [`premium-web-build`](skills/premium-web-build/SKILL.md) | Build a polished marketing site from a written spec. |
| [`motion`](skills/motion/SKILL.md) | Add or review UI animation and motion. |
| [`scroll-motion-debug`](skills/scroll-motion-debug/SKILL.md) | Fix scroll, pin, and section-transition animation bugs. |
| [`fixed-layout-qa`](skills/fixed-layout-qa/SKILL.md) | QA fixed layouts: PDFs, slides, brochures. |
| [`de-ai-production-pass`](skills/de-ai-production-pass/SKILL.md) | Final pass so a site doesn’t look AI-generated. |
| [`remove-ai-marks`](skills/remove-ai-marks/SKILL.md) | Strip AI watermarks / C2PA metadata from files. |
| [`aso`](skills/aso/SKILL.md) | Write or audit App Store listing copy, keywords, creatives. |

### Ship & quality

| Skill | What it does |
| --- | --- |
| [`ship`](skills/ship/SKILL.md) | Commit, push, and deploy when you’re ready to ship. |
| [`deploy-cloudflare`](skills/deploy-cloudflare/SKILL.md) | Deploy to Cloudflare Pages or Workers. |
| [`gitleaks-preflight`](skills/gitleaks-preflight/SKILL.md) | Unblock commits when secret scanners fail. |
| [`credential-sweep`](skills/credential-sweep/SKILL.md) | Find exposed secrets in local files safely. |
| [`test-coverage`](skills/test-coverage/SKILL.md) | Design tests or improve coverage (Python / JS / TS). |
| [`javascript-test-coverage`](skills/javascript-test-coverage/SKILL.md) | Run, fix, or raise JavaScript/TypeScript test coverage. |
| [`prompt-audit`](skills/prompt-audit/SKILL.md) | Clean up dated or redundant agent prompts and rules. |
| [`optimize`](skills/optimize/SKILL.md) | Make code or scripts faster, simpler, or cheaper to run. |

### Workflow

| Skill | What it does |
| --- | --- |
| [`grill-me`](skills/grill-me/SKILL.md) | Stress-test a plan with relentless questions. |
| [`ponytail`](skills/ponytail/SKILL.md) | Do the laziest thing that still works. |
| [`organize-mac-files`](skills/organize-mac-files/SKILL.md) | Rename, sort, or safely clean up Mac files. |
| [`maintain-skill-library`](skills/maintain-skill-library/SKILL.md) | Audit and keep your skill library tidy. |
| [`learned`](skills/learned/SKILL.md) | Load environment gotchas and hosting map when needed. |
| [`rtk`](skills/rtk/SKILL.md) | Handle huge command output without blowing the context. |
| [`letsfg`](skills/letsfg/SKILL.md) | Search flights or hotels via LetsFG. |

## Global rules

My always-on agent rules live in [`AGENTS.md`](AGENTS.md).

## Other skills I use (not in this repo)

I also install packs from other authors. Those stay upstream:

| Source | Examples |
| --- | --- |
| [emilkowalski/skills](https://github.com/emilkowalski/skills) | `apple-design`, `emil-design-eng`, animation skills |
| [mattpocock/skills](https://github.com/mattpocock/skills) | `grilling`, `code-review`, `tdd`, `implement`, `to-spec` |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | React best practices, web design guidelines |
| [referodesign/refero_skill](https://github.com/referodesign/refero_skill) | Upstream Refero skill (I also keep `refero-design` here) |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Frontend craft polish |

Full install list on a machine may be larger than this repo. That is intentional.

