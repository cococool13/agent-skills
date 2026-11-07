# Security

Always sketch trust boundaries for in-scope surfaces. Depth follows kind: a static marketing site gets headers, dependency and form sinks, and secret hygiene. An app or API also gets ASVS-style checks below. Use OWASP ASVS 5.0.0 (published 30 May 2025) as a requirement catalog (`v5.0.0-<id>`), not as a claim you completed the whole standard.

Write findings with actor, input, missing control, resource, and result. Authorized local fixture tests only.

## Headers and cookies (every kind)

- HTTPS, `Strict-Transport-Security` when you own the host.
- `Content-Security-Policy` delivered as a header (meta is weaker). Prefer a nonce- or hash-based strict CSP (`script-src` with nonces/hashes, `object-src 'none'`, `base-uri 'none'`) over a sprawling host allowlist; `'unsafe-inline'` and `'unsafe-eval'` defeat most XSS value (MDN CSP guide). Deploy new policies with `Content-Security-Policy-Report-Only` first so you do not break the live site — gradual compatibility.
- `frame-ancestors` (or `X-Frame-Options`) if the page should not be embedded.
- Cookie flags: `Secure`, `HttpOnly` where JS does not need the cookie, `SameSite` appropriate to the cross-site use. Distinguish first-party functional cookies from marketing cookies (see analytics module).
- CORS: explicit origins, not reflected `Origin` with credentials.

## When an app or API exists

- **Object-level auth / tenant isolation:** every handler that takes an object id checks that this caller may act on *that* object. UUIDs are not a check. Swap fixture ids across two users locally (OWASP API1:2023). Scope queries by tenant.
- **CSRF:** cookie-authenticated state changes need a token or equivalent; `SameSite` alone may be insufficient for your browser matrix.
- **XSS / injection / SSRF:** sanitize and encode; parameterized queries; server-side request URLs are allowlisted. Do not fetch attacker-controlled origins from the server.
- **Uploads:** type, size, and auth checks; stored files served with safe `Content-Type` and disposition (details in `08` if uploads exist).
- **Caching:** `Cache-Control` on authenticated or personalized responses does not leak tenant data via shared caches or CDNs.
- **Secrets:** env files noted, not printed; no tokens in client bundles or repo history you happen to open.

## Webhooks

If present, verify raw-body signatures, timestamp windows, and persist-or-enqueue *before* 2xx; return 5xx if that durable write fails. Duplicates fulfill once. See `08`.

### Recipe: object-id swap (apps/APIs only)

- **Prerequisites:** two fixture users, one object owned by B, the project's test harness. No production data.
- **Input:** authenticated as A, request B's id on list/read/update/delete.
- **Expected fail:** A reads or changes B's object.
- **Expected pass:** denial and no store change.
- **Artifact:** command output or a static handler → query path with no owner check.
- **ROI / stop:** each in-scope object type. Skip entirely on a static brochure.
