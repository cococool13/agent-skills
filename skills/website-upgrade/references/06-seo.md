# Indexability and truthful discovery

Open when the site is meant to be found in search, or claims to be private/`noindex`. Skip a logged-in-only app that is correctly `noindex`, and say so.

## Checks

- **Status and redirects:** the preferred host (https, www or apex) actually wins. Chains are short. HTTP to HTTPS is a real redirect. Do not use robots.txt as a canonicalization method (Google: it may still index the URL without content).
- **Canonicals:** `rel="canonical"` is a strong hint; sitemaps are a weaker one; redirects are stronger than both when retiring a URL (Google Search Central, updated 10 July 2026). Self-referential canonicals on the preferred URL. Absolute URLs. Do not point the sitemap, the header, and the `link` tag at three different URLs. Do not use URL fragments as canonicals. For JS apps, prefer the canonical in the HTML source and do not let client code silently change it.
- **robots:** `robots.txt` and `meta robots` / `X-Robots-Tag` match intent. Staging is not indexable. Do not block CSS/JS that Google needs to render a public page you want understood.
- **Sitemaps:** listed URLs are canonical, 200, and meant to be indexed.
- **Titles and descriptions:** unique enough to distinguish templates; match the visible page.
- **Structured data:** only markup that is visible and true. Google's structured data policies (updated 10 July 2026) forbid marking up hidden or misleading content (fake reviews, a how-to labeled as a recipe, content users cannot see). JSON-LD is fine when it restates the page. Do not invent FAQ, review, or product schema to look rich.
- **International:** `hreflang` clusters are reciprocal when you claim them.

Do not promise rankings.

### Recipe: verify a public URL's discovery signals

- **Prerequisites:** the preferred URL and any known duplicates (http, trailing slash, campaign params).
- **Input:** headers and HTML for those URLs (local preview or a fetch you are allowed to make).
- **Expected fail:** conflicting canonicals, an indexable staging host, or schema that describes something not on the page.
- **Expected pass:** one preferred URL, consistent signals, truthful or absent structured data.
- **Artifact:** `seo.md` or `evidence.md`.
- **ROI / stop:** templates and known duplicates, not every tag combination.
