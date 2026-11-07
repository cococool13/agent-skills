# Performance and Core Web Vitals

Open for user-facing pages. For a JSON-only API, note TTFB and payload size if relevant and skip visual vitals.

Core Web Vitals (web.dev, page updated 31 October 2024) are field metrics. Good thresholds at the **75th percentile**, segmented across mobile and desktop:

- **LCP** (loading): 2.5 seconds or faster
- **INP** (interactivity): 200 milliseconds or less
- **CLS** (visual stability): 0.1 or less

A page "passes" when all three meet those targets at p75. INP replaced FID as a stable Core Web Vital in 2024.

## Field versus lab

Lab data (Lighthouse, a local trace) uses one device, one network, and one geography. Field data (CrUX, RUM) is a distribution of real visits. They routinely disagree: cache hits, bfcache, personalization, fragment URLs, and when people interact all move LCP, INP, and CLS (see web.dev, "Why lab and field data can be different").

Rules for this skill:

- Prefer field numbers when they exist (Search Console, CrUX, or first-party RUM) to prioritize work.
- Use lab traces to debug a named journey on a stated network/device profile (for example "slow 4G, mid-tier phone"), not as a vanity score.
- Do not treat Lighthouse 100 as a goal. Do not report a lab LCP as "the site's LCP."
- Lighthouse cannot measure INP (no user). Total Blocking Time is only a lab proxy.
- Lab command, local or preview URL only: `npx --yes lighthouse@12.8.2 <url> --only-categories=performance --form-factor=mobile --output=json --output-path=<run>/lh-perf.json --chrome-flags=--headless=new`. Record the throttling profile it used.
- Name the source, the URL or page group, the percentile, and the device class for every number you cite.

## Budgets and costs

Write budgets in terms of outcomes people feel, then cost:

- LCP element: was it the hero image, a webfont heading, or a late-discovered block? Lab and field may pick different elements.
- Fonts: display strategy, number of families/weights, unused subsets.
- Images and video: dimensions reserved (CLS), modern formats, srcset, priority on the actual LCP candidate.
- JS and third parties: tag managers, chat, embeds — what they cost on the critical path.
- Layout: banners and cookie notices that shift content (CLS) or steal INP.
- Motion: honor `prefers-reduced-motion`; animation that blocks input is an INP issue.

If you cannot collect field data here, say so and use a single documented lab profile as `needs-validation` against production RUM.

### Recipe: record vitals without fetish scoring

- **Prerequisites:** a permitted preview or public URL; CrUX/PSI/RUM if reachable without paid quota the user did not approve.
- **Input:** the in-scope URL on a named lab profile, plus field p75 if available.
- **Expected fail:** only a single Lighthouse score is reported, or lab is labeled as field.
- **Expected pass:** LCP/INP/CLS (or TBT proxy) with source, percentile, and device class; the LCP candidate named.
- **Artifact:** `perf.md` or a section of `evidence.md`.
- **ROI / stop:** key templates, not every query-string variant. Stop when the next URL shares the same LCP and script graph.
