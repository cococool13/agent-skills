# Agent skills

Recipes that teach Cursor (and other coding agents) how I like work done.

You talk in plain English. The agent picks a matching skill and follows the steps.

---

## Start here (2 minutes)

1. Install [Cursor](https://cursor.com/) and a free [GitHub](https://github.com/) account.
2. In Terminal, run:

```bash
npx skills add cococool13/agent-skills --all -g -y
```

3. Open a project in Cursor and try one of the prompts below.
4. Optional: copy [`AGENTS.md`](AGENTS.md) into your project and change “Cohen” to your name. That file is the always-on rulebook.

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

## Skills worth knowing

### Design

- [`refero-design`](skills/refero-design/SKILL.md) — Research real app screens before inventing UI
- [`landing-page-design`](skills/landing-page-design/SKILL.md) — Design or revise a landing / marketing page
- [`redesign-existing-projects`](skills/redesign-existing-projects/SKILL.md) — Upgrade an existing site’s look, UX, or quality
- [`premium-web-build`](skills/premium-web-build/SKILL.md) — Build a polished marketing site from a written spec
- [`motion`](skills/motion/SKILL.md) — Add or review UI animation
- [`de-ai-production-pass`](skills/de-ai-production-pass/SKILL.md) — Final pass so a site doesn’t look AI-generated

### Ship

- [`ship`](skills/ship/SKILL.md) — Commit, push, and deploy when you’re ready
- [`deploy-cloudflare`](skills/deploy-cloudflare/SKILL.md) — Deploy to Cloudflare Pages or Workers
- [`test-coverage`](skills/test-coverage/SKILL.md) — Design tests or improve coverage

### Thinking

- [`grill-me`](skills/grill-me/SKILL.md) — Stress-test a plan with hard questions

Click any name for the full recipe.

---

## Also useful

- **Always-on rules:** [`AGENTS.md`](AGENTS.md)
- **Hosting I use:** Cloudflare Pages / Workers
- **Extra skills from other people:** [Emil](https://github.com/emilkowalski/skills) · [Matt Pocock](https://github.com/mattpocock/skills) · [Vercel labs](https://github.com/vercel-labs/agent-skills) · [Impeccable](https://github.com/pbakaus/impeccable)

The install command may add a few extra personal/ops skills I use day to day (file cleanup, secret scans, travel search, etc.). They’re in the repo for me — not the ones to learn first.
