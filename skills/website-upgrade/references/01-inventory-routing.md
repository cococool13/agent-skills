# Inventory, baseline, and kind routing

Walk the scoped tree once. Write `map.md` and `coverage.md`. Infer one or more kinds; a property can be mixed (brochure plus an API).

## Detect kind

| Kind | Typical signals | Load | Do not load |
| --- | --- | --- | --- |
| Static / marketing | HTML/CSS/MDX, no server auth, no CMS collections, form posts to a third party or `mailto:` | Journeys (lite), accessibility, responsive, design, performance, SEO if public, security headers, analytics, resilience (404/redirects/back) | Object-level API tests, CSRF session suites, webhook inbox tests, SSR hydration, Worker bindings, uploads, tenant isolation |
| CMS / Webflow | CMS schema, collection slugs, `webflow.json`, WP themes, visual editor config | Everything for static/marketing, plus read-only platform notes in `08` | Publish, live collection writes, inventing CMS fields |
| SPA / SSR app | Next/Remix/Nuxt/SvelteKit, session auth, server actions, hydration | Journeys, a11y, design, performance, SEO as applicable, full security, resilience including hydration | Treating every marketing page as an authenticated app |
| Worker / server API | `wrangler.toml`, `routes`, OpenAPI, queue consumers, webhooks | Security (auth, BOLA, injection, SSRF, cache), reliability (retries, webhooks, uploads) | Forcing Lighthouse, design-polish, or VoiceOver passes on a JSON-only worker |

If mixed, apply each row only to the matching surfaces. Record the inference and the signals in `map.md`.

## Inventory

1. Read README, deploy config, package manifests, and CMS or Worker config that is already in the repo. Remote dashboards stay read-only.
2. List entry points in scope: pages, routes, server actions, form actions, webhooks, workers, cron, sitemaps, well-known files.
3. For each, name actor, input, writes, outbound calls, and success result. Mark money, auth, personal data, and outbound messaging.
4. List implicit state: multi-step forms, cart/checkout, auth, feature flags, cookie banners, loading/empty/error.
5. Write `coverage.md`: inspected globs and explicit gaps. A skipped generated or vendored tree is a gap, not "fine." Do not claim every file was reviewed.

Do not open secret files. Record that a secret-looking path exists without printing values.

### Recipe: map a surface

- **Prerequisites:** repo docs, route tables, CMS schema if present.
- **Input:** one concrete entry (`GET /pricing`, `POST /api/pairs`, a Webflow collection template).
- **Expected fail:** the map omits a writer, outbound call, or actor.
- **Expected pass:** actor, input, writes, outbound calls, and success are named.
- **Artifact:** a row in `map.md`.
- **ROI / stop:** every reachable in-scope entry. Stop when a scoped search adds no row.

## Baseline

Run only the project's documented gates (test, lint, typecheck, build). Record command and counts in `evidence.md` (or `baseline.md` if the output is long). A static marketing folder with no test script gets one line: `no documented local gate`, not a fake suite.

If dependencies are missing, run the repo's own lockfile install (`npm ci`, `pnpm install --frozen-lockfile`, and so on) when house rules allow project-local installs; otherwise ask. Never install globally or update a lockfile to make a gate run. Otherwise record `needs <toolchain>`. Do not claim an unrun check passed. Later work must not make recorded counts worse.

## Stop

`map.md` names kind(s), modules loaded, and modules not loaded. `coverage.md` lists gaps. Baseline has real commands or a clear reason none exist.
