---
name: premium-web-build
description: "Use when building or extending a polished marketing or business website from a specification."

---

# Premium Web Build

Cohen is a UGA student shipping real, sellable client sites with AI. Sites must
look hand-crafted and **never "AI-generated."** Ship polished from the first pass.

## Stack (from global agent rules — confirm per project)
- **Marketing / mostly-static:** Astro + Tailwind (lighter than Next).
- **App-like / interactive:** Next.js App Router + React + strict TS + Tailwind + shadcn/ui.
- **Motion:** GSAP (+ ScrollTrigger), Lenis smooth scroll, Three.js / WebGL for 3D.
- **Backend/DB/auth:** Supabase + Drizzle.
- **Read versions from the project's `package.json`.** Do not carry version numbers
  in this file — they go stale (this skill said "Astro 6" while Spiral ran Astro 7).
- Pin Three.js to a CDN-safe version; reuse one Lenis instance and render off the
  single `gsap.ticker` — never spin up a second rAF loop.

## Hosting is per-project — check before you assume
| Project | Host |
|---|---|
| Spiral Collection / spiral-brief (old spiral-demo) | **Cloudflare Pages** (`spiralcc.tech` / `spiraldemo.pages.dev`). Not the portfolio — that is `cococool13/portfolio` at https://cohencool.com |
| Coastal PharmaCare | **Cloudflare Pages** |
| Coastal Hardware New Build, ENTR, JCC forms/evaluator, PropScanner web | **Cloudflare Workers** |
| JCC SECURE | **Firebase** |
| Coastal Hardware (old Next checkout) | **retired** — do not deploy |

Read the project's `CLAUDE.md`, then `deploy-cloudflare`.
A leftover `netlify.toml` or `vercel.json` is not the live host. Never migrate
a site between hosts.

## Spec discipline (do this first, every time)
1. **Read the project's brief files COMPLETELY before writing anything** —
   `AGENTS.md` / `CLAUDE.md`, then `BRAND.md`, `SPEC.md`/`BUILD_PROMPT.md`, `DESIGN.md`,
   `STRUCTURE.md`, `MOTION.md`, and any logo SVGs in the folder.
2. Treat the brief's "non-negotiables" / motion law / CSS-variable names as
   binding. Use the exact token names and values (e.g. `--ink`, accent ramp
   `--acid → --cyan → --peri`; Fraunces headlines large + low weight + tight
   tracking; mono eyebrows above serif headlines; accent used sparingly).
3. Pull editable copy + lists into ONE content source (Astro content collection
   or typed content config) so text/links are editable without touching logic.

## Build loop
- Work in milestones/phases; **commit after each step so Cohen can review.**
- Don't claim done without checking — use the `ego-browser` skill:
  take desktop + mobile screenshots, verify against BRAND.md, fix what you find.
- Files < 800 lines; immutability; brief "why" then code (he's learning).
- Decide ambiguity yourself and proceed; don't over-ask. Diagnose-and-fix bugs.

## Motion conventions (the "motion law")
Subtle over showy. Ambient backgrounds (DNA/helix, WebGL shaders) sit BEHIND
content and must never hurt text contrast — add a radial scrim behind text-heavy
blocks. On mobile (≤768px) reduce parallax intensity, disable the custom cursor,
and ensure no horizontal overflow from pinned/horizontal galleries. Respect
autoplay policy for any audio (off by default, user-gesture to start, accessible
toggle). Responsive QA at 380 / 768 / 1280.

## Parallel "v2" redesigns
Cohen often asks for a bold, constraints-off B-version to test against the
conservative v1. When he does: **build v2 fully separate, never touch v1.** Use a
separate dir or git worktree; keep both deployable.

## Deploy / handoff
Do not run `netlify deploy --prod` for Spiral. Do the work here rather than
handing off prompts unless asked. When a site is "done", run
`de-ai-production-pass` before presenting it to a client. End by telling him
exactly what he still needs to edit (env vars, domain, placeholders).

## Related skills (don't duplicate)
- `code-review` — pre-merge quality/security pass.
- `de-ai-production-pass` — the final hardening + de-AI + sellability pass.

## Single-feature worktree loop (the dominant Spiral pattern)
Most Spiral work adds ONE ambient/motion feature per git worktree (preloader,
ambient audio, accent migration, 3D DNA background, scroll-velocity skew, helix
interactivity, WebGL shader). Standard loop for these:
1. Branch/worktree for the one feature; read AGENTS.md / CLAUDE.md + BRAND.md first.
2. Implement reusing the EXISTING Lenis instance and `gsap.ticker` — **never add a
   new rAF loop**. Keep it behind content; subtle over showy.
3. Honor the cross-cutting conventions without restating them: contrast scrim
   behind text over animated backgrounds; reduce parallax + disable custom cursor
   ≤768px; no horizontal overflow; audio off-by-default with accessible toggle.
4. QA with `ego-browser`: full-page screenshot at 1280 and 380, verify
   legibility and no regressions, then commit.
