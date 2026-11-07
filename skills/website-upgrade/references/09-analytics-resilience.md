# Analytics, consent, and resilience

## Analytics and consent

- List analytics, ads, and tag-manager loads you can see in the repo or page. Note whether they run before consent.
- Functional measurement (did the form work?) should not require a marketing pixel. Deduplicate page views and conversions if two tags fire the same event.
- Do not invent a privacy policy, retention period, or legal basis. If consent copy and actual behavior disagree, that is a finding.
- Do not send extra events to a live property "to see if it works."

PII: look for emails, names, or tokens in event payloads and logs. Redact; do not print values you find.

## Resilience

Walk these when they apply. Skip hydration notes on a static HTML site.

| Case | What to check |
| --- | --- |
| Redirects | Old paths cited in the repo or sitemap land somewhere useful |
| 404 | Custom page in brand; no soft-404 for important retired URLs that should 301 |
| Offline / flaky network | What the app claims (PWA) versus a blank hang |
| Loading / empty / error | Designed states; errors that the user can recover from |
| Hydration | SSR markup matches the first client render on in-scope pages; no flash of broken auth |
| Back | Browser back does not resurrect a submitted form as a silent duplicate if you can tell from code |
| Deep links | Documented URLs restore the right page and state; unknown slugs 404 cleanly |

### Recipe: deep link and 404

- **Prerequisites:** router table or hosted redirects file.
- **Input:** a known-good deep link and a nonsense path.
- **Expected fail:** nonsense path renders a 200 homepage, or a documented link 404s.
- **Expected pass:** documented links resolve; unknown paths are a real 404 (or the product's documented equivalent).
- **Artifact:** notes in `evidence.md`.
- **ROI / stop:** each route family, not every slug.
