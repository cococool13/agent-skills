---
name: deploy-cloudflare
description: "Use when deploying Cohen's sites to Cloudflare Pages or Workers."
---

# Deploy to Cloudflare

Default hosting for this pack is Cloudflare. Read the project's `AGENTS.md` first —
they win on commands, project name, and secrets.

## Example host map (author's projects — replace with yours)

| Site | Host |
| --- | --- |
| Spiral Collection, spiral-brief, Portfolio | Pages |
| ENTR, JCC forms/evaluator/SECURE/calculators | Workers |

## Pick the mode from the repo

| Signal | Mode |
| --- | --- |
| `wrangler.jsonc` with `pages_build_output_dir` | **Pages** |
| `wrangler.jsonc` with `assets.directory` or Worker `main` | **Workers** (static assets or OpenNext/Express) |
| GitHub Action running `wrangler pages deploy` | Prefer push to `main` if CI already deploys |

## Pre-deploy

1. `git status` — commit or stash first.
2. `bash ~/.agents/skills/gitleaks-preflight/scripts/preflight.sh` — must pass before deploy (Cursor scans the working tree too).
3. Run the project's verify/build gate if documented (`npm run verify:full`,
   `pnpm build`, etc.).
4. Confirm Wrangler sees the right account: `npx wrangler whoami`.

## Pages (example: spiral-brief, Spiral Collection site)

Pin `wrangler` in `devDependencies` and use `npm run deploy` locally — avoids a fresh `npx` download every deploy. CI may keep `npx wrangler@4` if you prefer.

```bash
npm run build   # or pnpm build — use the project's package manager
npx wrangler pages deploy <outdir> --project-name=<name> --branch=main
```

Typical names: `spiraldemo`, `spiral-collection`. Output
dirs are usually `dist` or `out` — read `AGENTS.md` / `wrangler.jsonc`.

## Workers static assets (entr-website)

```bash
npx wrangler deploy
```

Check `.assetsignore` before deploy so `.env*`, `_archive/`, and `*.md` are not
uploaded.

## Workers apps (JCC forms, evaluator)

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

Open the workers.dev / pages.dev URL from the deploy output in the browser that
`~/.agents/AGENTS.md` routes to: the built-in browser pane in the Claude desktop
app, `ego-browser` in other clients. Use the client's Chrome tools when the check
needs Cohen's logged-in Cloudflare session.
Confirm the change on the real page, not just HTTP 200. If no browser connects,
say the browser check did not run.

## Common failures

- Wrong project name → deploys to an empty/scratch Worker
- Missing `nodejs_compat` / wrong compatibility date on Workers apps
- CSP / `_headers` hashes stale after editing inline scripts
- Uploading secrets because `.assetsignore` was incomplete
