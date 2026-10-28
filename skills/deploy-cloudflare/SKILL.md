---
name: deploy-cloudflare
description: "Use when deploying Cohen's sites to Cloudflare Pages or Workers."
---

# Deploy to Cloudflare

Default hosting for this pack is Cloudflare. Read the project's `AGENTS.md` first.
They win on commands, project name, and secrets.

## Account

Wrangler is logged in as `cohencool@icloud.com` on account **The Mecca**
(`22dc27cd1d3824d6f131d8057a172c68`). The workers.dev subdomain is `cohencool`.

Agents operate the account with the Cloudflare Code Mode MCP at
`https://mcp.cloudflare.com/mcp`. Call `search`, then `execute`. `docs` searches
the docs. Grok's server name is `cloudflare`. Claude's is `cloudflare-api`.
Codex's is `cloudflare`. Cursor's is `cloudflare-api` in `~/.cursor/mcp.json` (plugin Cloudflare MCPs stay empty/disabled). Leave `cloudflare-bindings`, `cloudflare-builds`, and
`cloudflare-observability` disabled. Those servers repeat the same API as
thousands of tools.

The MCP token can read and change DNS, Access, Workers, Pages, D1, KV, R2, and
email. Wrangler login cannot list DNS records. Pass `account_id` on `execute`
when the tool asks for it.

`~/Projects/TBP Website` targets the Backpack Project account. Do not deploy
that folder onto The Mecca.

New sites are Workers with static assets. Leave the Pages projects below as Pages.

## Host map

| Project | Cloudflare name | Public host |
| --- | --- | --- |
| Portfolio | Pages `cohen-portfolio` | `cohencool.com`, `www` |
| Spiral Collection | Pages `spiral-collection` | `spiralcc.tech` |
| Allie | Pages `cohen-loves-allie` | `cohenlovesallie.com`. Deploy only when asked |
| Pivot | Pages `pivot` | `pivot-5sx.pages.dev` |
| Quire | Pages `quire` | `quire-ebz.pages.dev` |
| Cesura (Baton/site) | Pages `cesura` | `cesura.pages.dev` |
| Agent Shelf, Prompt Gallery | Pages `agentshelf`, `prompt-to-app-gallery` | `*.pages.dev`. Source is not under `~/Projects` |
| Azukari | Worker `they-hold` | `azukari.app` |
| Spiral Ship | Worker `spiralship-site` | `spiralship.com` |
| Berth | Worker `berth` | `berth.cohencool.com` |
| Lumen | Worker `lumen` | `lumen.cohencool.com` |
| Halo | Worker `halo-api` | `cohencool.com/halo*` only |
| licensing | Worker `licensing` | `licensing.cohencool.workers.dev` |
| spiral-license | Worker `spiral-license` | service binding in front of `licensing` for old builds. Keep it |

Other product sites are Workers named in that project's `wrangler.jsonc` and
served at `<name>.cohencool.workers.dev`. `tweakeazy.pages.dev` redirects to
Worker `tweakeazy-site`. The portfolio links the Worker.

`stacks` is the private index and stays behind Access. `stacks-web`,
`stacks-auth`, `stacks-mcp`, and `stacks-site` are the other Stacks app. Do not
merge them. Access also covers `dashboard.cohencool.workers.dev` and the signed
`stacks.cohencool.workers.dev/i/*` bypass.

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

- Wrong project name deploys a scratch Worker. JCC Retirement Plan Evaluator is
  the known case: `npm run deploy:jcc` and `npm run deploy:newedge` only. A bare
  `wrangler deploy` writes `jcc-evaluator-dev` and misses both client sites.
- `Overheard` and `Overheard-mvp` both deploy Worker `overheard-preview`.
- Do not deploy from `Utter/build-*`, `licensing-quire`, `stacks-cloud-deploy`,
  or `stacks-private-eval`. Those trees copy live Worker names.
- Missing `nodejs_compat` / wrong compatibility date on Workers apps
- CSP / `_headers` hashes stale after editing inline scripts
- Uploading secrets because `.assetsignore` was incomplete
