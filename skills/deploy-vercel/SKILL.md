---
name: deploy-vercel
description: "Use when a project's CLAUDE.md says the live host is still Vercel. Most Cohen sites are Cloudflare Workers or Pages — follow that project's CLAUDE deploy section instead."
---

# Deploy to Vercel (rare)

Past deploys stalled on "command not found" and "ERROR: vercel CLI not installed."
The fix is to never assume a global `vercel` binary — always invoke through
`pnpm dlx` (or `npx`).

## Check the platform first (required)

Read the project's `CLAUDE.md` / `AGENTS.md` deploy section and stop if the live
host is not Vercel.

Current map (2026-08):

- Spiral Collection / spiral-brief → **Cloudflare Pages**
- Coastal PharmaCare → **Cloudflare Pages**
- Coastal Hardware New Build / entr-website / JCC forms & evaluator / PropScanner web → **Cloudflare Workers**
- JCC SECURE → **Firebase**
- Coastal Hardware (old Next checkout) → **retired** — do not deploy

If the repo has `wrangler.jsonc`, `wrangler.toml`, `firebase.json`, or Cloudflare
CI, follow that project's docs — **not** this skill.

## Never assume a global CLI

Use `pnpm dlx vercel ...` (or `npx vercel ...` if pnpm is missing):

```bash
pnpm dlx vercel --version
```

## Pre-deploy checks

1. Clean tree: `git status` — commit/stash before deploying.
2. Build locally first:
   ```bash
   pnpm install
   pnpm build
   ```
3. Confirm output dir and that images/logos resolve.

## Deploy

```bash
pnpm dlx vercel link        # first time
pnpm dlx vercel             # preview
pnpm dlx vercel --prod      # production — confirm first if tree is dirty
```

Env vars:

```bash
pnpm dlx vercel env add <NAME> production
```

## Verify after deploy

Open the returned URL with the web QA path from user rules (`ego-browser` / Ego Lite). Screenshot at 1280 and 380. Do not use Cursor browser MCP as a substitute.
Confirm hero/logos/images, not just HTTP 200. Report the live URL.

## Common failures

- Bare `vercel` → use `pnpm dlx vercel`
- Local OK, prod 404 → wrong output dir / base path
- Missing images → case-sensitive paths on Linux hosts

## Guardrails

Commit first, never force-push, confirm before `--prod` with uncommitted work.
