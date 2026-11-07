# Public sources

Curated public references for the website-upgrade skill. No private account data, bookmarks, or identity.

Retrieved 2026-11-07 (America/New_York) unless a publication date is listed. **Opened** means a primary page was read; **located** means the URL exists but the body was thin or only partly used.

Engineering practices reused from the 2026-11-07 app-upgrade research (persist-before-ack webhooks, object-level authorization, risk-ranked formal methods, evidence types) are applied here only where a site actually has those surfaces.

## Performance

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [Web Vitals / Core Web Vitals](https://web.dev/articles/vitals) | Updated 31 Oct 2024 | LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1 at p75, mobile and desktop; INP is a stable Core Web Vital; field first; Lighthouse cannot measure INP (use TBT as a lab proxy) | opened |
| [Why lab and field data can be different](https://web.dev/articles/lab-and-field-data-differences) | Page footer 18 Jul 2022; body discusses INP (opened 2026-11-07) | Lab is one device/network; field is a distribution; cache, bfcache, personalization, and interaction change LCP/INP/CLS | opened |

## Accessibility

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [What's New in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/) | WCAG 2.2 Recommendation, 5 Oct 2023 | Nine added success criteria; 4.1.1 Parsing removed; 2.4.11, 2.5.7, 2.5.8, 3.2.6, 3.3.7, 3.3.8 summarized from the page | opened |

## SEO and structured data

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [Specify a canonical URL](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) | Updated 10 Jul 2026 | Redirects > `rel=canonical` > sitemap as signals; do not canonicalize with robots.txt; self-referential canonicals; absolute URLs | opened |
| [Structured data policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies) | Updated 10 Jul 2026 | Markup must match visible, truthful content; no hidden or misleading schema | opened |

## Security

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/) | 5.0.0 published 30 May 2025 | Requirement catalog (`v5.0.0-<id>`); not a claim the whole standard was completed | opened |
| [MDN: Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP) | current MDN (opened 2026-11-07) | Header vs meta; strict nonce/hash CSP; deploy with report-only; `'unsafe-inline'` weakens XSS defense | opened |
| [OWASP API1:2023](https://raw.githubusercontent.com/OWASP/API-Security/master/editions/2023/en/0xa1-broken-object-level-authorization.md) | 2023 edition | Object-level authorization; UUID is not a substitute (apps/APIs only) | opened in prior research; still cited |
| [Stripe webhooks](https://docs.stripe.com/webhooks) | current docs | Raw-body signatures. This skill still requires persist-or-enqueue before 2xx | opened in prior research |

## Skill format

Public skill-format notes (Agent Skills spec, Anthropic best practices, ChatGPT build-skills) informed the entrypoint shape. See the sibling app-upgrade comparison packet if present; those URLs are not required to run this skill.
