---
name: deploy-cloudflare
description: "Use when deploying Cohen's sites to Cloudflare Pages or Workers (Spiral, Coastal PharmaCare, Coastal Hardware New Build, entr-website, JCC forms/evaluator, PropScanner web). Prefer this over deploy-vercel unless CLAUDE.md says the live host is still Vercel."
---

# Deploy to Cloudflare

Most of Cohen's live sites are Cloudflare. Read the project's `CLAUDE.md` first —
it wins on commands, project name, and secrets.

## Host map

| Site | Host |
| --- | --- |
| Spiral Collection, spiral-brief, Coastal PharmaCare | Pages |
| Coastal Hardware New Build, entr-website, JCC Retirement Plan Evaluator, jcc-client-forms, Prize Picks Board (PropScanner) | Workers |
| JCC SECURE | Firebase |
| Coastal Hardware (old checkout) | retired |
| JCC Retirement Plan Evaluator vercel.json | stale; live host is Workers |


## Pick the mode from the repo

| Signal | Mode |
| --- | --- |
| `wrangler.jsonc` with `pages_build_output_dir` | **Pages** |
| `wrangler.jsonc` with `assets.directory` or Worker `main` | **Workers** (static assets or OpenNext/Express) |
| GitHub Action running `wrangler pages deploy` | Prefer push to `main` if CI already deploys |

Never assume Vercel. `deploy-vercel` is only for repos whose `CLAUDE.md` still
names Vercel as live.

## Pre-deploy

1. `git status` — commit or stash first.
2. `bash ~/.agents/skills/gitleaks-preflight/scripts/preflight.sh` — must pass before deploy (Cursor scans the working tree too).
3. Run the project's verify/build gate if documented (`npm run verify:full`,
   `pnpm build`, etc.).
4. Confirm Wrangler sees the right account: `npx wrangler whoami`.

## Pages (example: spiral-brief, Coastal PharmaCare, Spiral Collection site)

```bash
npm run build   # or pnpm build — use the project's package manager
npx wrangler pages deploy <outdir> --project-name=<name> --branch=main
```

Typical names: `spiraldemo`, `coastal-pharmacare`, `spiral-collection`. Output
dirs are usually `dist` or `out` — read `CLAUDE.md` / `wrangler.jsonc`.

## Workers static assets (Coastal Hardware New Build, entr-website)

```bash
npx wrangler deploy
```

Check `.assetsignore` before deploy so `.env*`, `_archive/`, and `*.md` are not
uploaded.

## Workers apps (JCC forms, evaluator, PropScanner OpenNext)

Follow the project's scripts (`npm run deploy`, `opennextjs-cloudflare deploy`,
`wrangler deploy --env jcc`). Named `--env` values matter — a bare deploy can
hit a scratch Worker.

## Secrets

Never put secrets in `wrangler.jsonc`. Use:

```bash
npx wrangler pages secret put <NAME> --project-name=<name>
# or
npx wrangler secret put <NAME>
```

Name vars only; do not print values.

## Verify

Open the workers.dev / pages.dev URL from deploy output. Use the `ego-browser`
skill (Ego Lite / `ego-browser` CLI). **Before screenshots**, unminimize the agent
window — paste `ensureAgentWindow` from `~/.agents/skill-overlays/ego-browser/references/agents.md`
(or run `bash ~/.agents/skill-overlays/ego-browser/scripts/health-check.sh`).
`captureScreenshot()` returns a **file path**, not bytes. Confirm the change on a
real page, not just HTTP 200. Do not use Cursor browser MCP as a substitute.

## Common failures

- Wrong project name → deploys to an empty/scratch Worker
- Missing `nodejs_compat` / wrong compatibility date on Workers apps
- CSP / `_headers` hashes stale after editing inline scripts
- Uploading secrets because `.assetsignore` was incomplete
