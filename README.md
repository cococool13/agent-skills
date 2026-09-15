# Agent skills

Recipes that teach Cursor (and other coding agents) how work should get done.

You talk in plain English. The agent picks a matching skill and follows the steps.

Skills are written so **other people can use them**. A few files still include the author’s example paths or project names — swap those for yours (or ignore them). His live `AGENTS.md` / `CONTEXT.md` keep his personal defaults without locking the recipes to one person.

---

## Start here (2 minutes)

1. Install [Cursor](https://cursor.com/) and a free [GitHub](https://github.com/) account.
2. In Terminal, run:

```bash
npx skills add cococool13/agent-skills --all -g -y
```

3. Open a project in Cursor and try one of the prompts below.
4. Optional: copy [`AGENTS.md`](AGENTS.md) into your setup and change names/paths to match you.

Update later: `npx skills update -g -y`

---

## Try saying this

| You want… | Say something like… | Skill |
| --- | --- | --- |
| A stronger plan before building | “Grill me on this idea” | [`grill-me`](skills/grill-me/SKILL.md) |
| UI that doesn’t look made up | “Use Refero and design this screen” | [`refero-design`](skills/refero-design/SKILL.md) |
| A landing page | “Design a landing page for …” | [`landing-page-design`](skills/landing-page-design/SKILL.md) |
| Less “AI-looking” polish | “Do a de-AI production pass” | [`de-ai-production-pass`](skills/de-ai-production-pass/SKILL.md) |
| To put it live | “Ship this to Cloudflare” | [`ship`](skills/ship/SKILL.md) · [`deploy-cloudflare`](skills/deploy-cloudflare/SKILL.md) |

You usually don’t type the skill name. Just describe the job.

---

## All skills

### Design

- [`refero-design`](skills/refero-design/SKILL.md) — Research real app screens before inventing UI
- [`landing-page-design`](skills/landing-page-design/SKILL.md) — Design or revise a landing / marketing page
- [`redesign-existing-projects`](skills/redesign-existing-projects/SKILL.md) — Upgrade an existing site’s look, UX, or quality
- [`premium-web-build`](skills/premium-web-build/SKILL.md) — Build a polished marketing site from a written spec
- [`motion`](skills/motion/SKILL.md) — Add or review UI animation
- [`scroll-motion-debug`](skills/scroll-motion-debug/SKILL.md) — Fix scroll / pin / section-transition bugs
- [`fixed-layout-qa`](skills/fixed-layout-qa/SKILL.md) — QA PDFs, slides, and other fixed layouts
- [`de-ai-production-pass`](skills/de-ai-production-pass/SKILL.md) — Final pass so a site doesn’t look AI-generated
- [`remove-ai-marks`](skills/remove-ai-marks/SKILL.md) — Strip AI watermarks / C2PA metadata
- [`aso`](skills/aso/SKILL.md) — App Store listing copy, keywords, creatives

### Ship & quality

- [`ship`](skills/ship/SKILL.md) — Commit, push, and deploy when you’re ready
- [`deploy-cloudflare`](skills/deploy-cloudflare/SKILL.md) — Deploy to Cloudflare Pages or Workers
- [`gitleaks-preflight`](skills/gitleaks-preflight/SKILL.md) — Unblock commits when secret scanners fail
- [`credential-sweep`](skills/credential-sweep/SKILL.md) — Find exposed secrets in local files
- [`test-coverage`](skills/test-coverage/SKILL.md) — Design tests or improve coverage
- [`javascript-test-coverage`](skills/javascript-test-coverage/SKILL.md) — JS/TS tests and coverage
- [`prompt-audit`](skills/prompt-audit/SKILL.md) — Clean up dated agent prompts and rules
- [`optimize`](skills/optimize/SKILL.md) — Make code faster, simpler, or cheaper to run

### Workflow

- [`grill-me`](skills/grill-me/SKILL.md) — Stress-test a plan with hard questions
- [`ponytail`](skills/ponytail/SKILL.md) — Do the laziest thing that still works
- [`organize-mac-files`](skills/organize-mac-files/SKILL.md) — Rename, sort, or safely clean up Mac files
- [`maintain-skill-library`](skills/maintain-skill-library/SKILL.md) — Keep your skill library tidy
- [`learned`](skills/learned/SKILL.md) — Environment gotchas / skill routing when needed
- [`rtk`](skills/rtk/SKILL.md) — Handle huge command output without filling the chat
- [`letsfg`](skills/letsfg/SKILL.md) — Search flights or hotels via LetsFG

Click any name for the full recipe.

---

## Also useful

- **Always-on rules template:** [`AGENTS.md`](AGENTS.md)
- **Extra skills from other people:** [Emil](https://github.com/emilkowalski/skills) · [Matt Pocock](https://github.com/mattpocock/skills) · [Vercel labs](https://github.com/vercel-labs/agent-skills) · [Impeccable](https://github.com/pbakaus/impeccable)
