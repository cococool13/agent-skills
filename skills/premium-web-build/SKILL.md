---
name: premium-web-build
description: "Use when building or extending a polished marketing or business site from a specification."

---

# Premium Web Build

Ship sellable, hand-crafted client sites. Never look AI-generated. Prefer polished from the first pass.

## Stack (confirm per project)

- Marketing / mostly-static: Astro + Tailwind
- App-like: Next.js App Router + React + strict TS + Tailwind + shadcn/ui when the project already uses them
- Motion: GSAP (+ ScrollTrigger), Lenis, Three.js / WebGL when needed — one Lenis instance, one `gsap.ticker` (never a second rAF loop)
- Backend: Supabase + Drizzle when the project needs it
- Versions: read `package.json`. Host: project `CLAUDE.md` → `deploy-cloudflare`. Live map: `~/.agents/CONTEXT.md`

A leftover `netlify.toml` or `vercel.json` is not the live host.

## Spec discipline

1. Read project brief files that exist (`AGENTS.md` / `CLAUDE.md`, `BRAND.md`, `SPEC.md` / `BUILD_PROMPT.md`, `DESIGN.md`, `STRUCTURE.md`, `MOTION.md`, logos) before writing.
2. Treat brief non-negotiables, motion law, and CSS token names as binding.
3. Keep editable copy in one content source.

## Build loop

- Smallest useful milestones; verify with `ego-browser` (380 / 768 / 1280) before claiming done.
- Decide ambiguity and proceed; diagnose-and-fix bugs.
- Parallel bold "v2" redesigns: separate dir or worktree — never touch v1.

## Motion law

Subtle over showy. Ambient/WebGL behind content with a contrast scrim under text. On ≤768px: reduce parallax, disable custom cursor, no horizontal overflow. Audio off by default.

## Related

- Landing strategy/visual system for conversion pages: `landing-page-design`
- Final client pass: `de-ai-production-pass`
- Craft polish after direction: `impeccable` / `emil-design-eng` (via `motion` or learned routing)
