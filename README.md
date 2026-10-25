# Agent skills

Recipes for Cursor and other coding agents. Talk in plain English; the agent picks a matching skill.

A few files still include example paths — swap those for yours. Keep personal defaults in your own `~/.agents/AGENTS.md`.

---

## Start here (2 minutes)

1. Install [Cursor](https://cursor.com/) and a free [GitHub](https://github.com/) account.
2. In Terminal, run:

```bash
npx skills add cococool13/agent-skills --all -g -y
```

3. Open a project in Cursor and try one of the prompts below.

Keep always-on rules in **your** `~/.agents/AGENTS.md`. This repo’s `AGENTS.md`
is a pointer only — do not copy global rules into it.

Update later: `npx skills update -g <name>` after reviewing the change

---

## Try saying this

| You want… | Say something like… | Skill |
| --- | --- | --- |
| A new app or site, done right | “Start a new build for …” | [`new-build-recipe`](skills/new-build-recipe/SKILL.md) |
| A whole-repo audit and cleanup PR | “Run repo-upgrade on this repo” | [`repo-upgrade`](skills/repo-upgrade/SKILL.md) |
| To put it live | “Ship this to Cloudflare” | [`ship`](skills/ship/SKILL.md) · [`deploy-cloudflare`](skills/deploy-cloudflare/SKILL.md) |

You usually don’t type the skill name. Just describe the job.

---

## All skills

### Build & ship

- [`new-build-recipe`](skills/new-build-recipe/SKILL.md) — Start a new product build: reference, design refs, build, guardrails
- [`ship`](skills/ship/SKILL.md) — Commit, push, and deploy when you’re ready
- [`deploy-cloudflare`](skills/deploy-cloudflare/SKILL.md) — Deploy to Cloudflare Pages or Workers
- [`gitleaks-preflight`](skills/gitleaks-preflight/SKILL.md) — Unblock commits when secret scanners fail
- [`repo-upgrade`](skills/repo-upgrade/SKILL.md) — Full repo audit + fix: ponytail, Cloudflare security-audit, scanners, one draft PR

### Agent setup

- [`create-hook`](skills/create-hook/SKILL.md) — Create or repair lifecycle hooks for Codex, Cursor, Claude Code, or Grok
- [`canvas`](skills/canvas/SKILL.md) — Create or edit a `.canvas.tsx` artifact
- [`maintain-skill-library`](skills/maintain-skill-library/SKILL.md) — Keep your skill library tidy

### From their authors

These used to be copied here. Install them from the source so you get updates:

- [`refero-design`](https://github.com/referodesign/refero_skill) — Research real app screens before inventing UI
- [`motion`](https://github.com/motiondivision/ai-kit) — Add or review UI animation (`npx motion-ai`)
- [`ponytail`](https://github.com/DietrichGebert/ponytail) — Do the laziest thing that still works
- [`aso`](https://github.com/alexszczurek/before-skills) — App Store listing copy, keywords, creatives
- [`grilling`](https://github.com/mattpocock/skills) — Stress-test a plan with hard questions (replaces `grill-me`)

Click any name for the full recipe.

---

## Also useful

- **Personal always-on rules:** `~/.agents/AGENTS.md` (not this repo)
- **Extra skills from other people:** [Emil](https://github.com/emilkowalski/skills) · [Matt Pocock](https://github.com/mattpocock/skills) · [Vercel labs](https://github.com/vercel-labs/agent-skills) · [Impeccable](https://github.com/pbakaus/impeccable)
