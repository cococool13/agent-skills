# Threat model

Write `threats.md` before you hunt. A paragraph is enough for `--quick`. `--deep` lists every in-scope trust boundary.

## Sketch

For the in-scope system, name:

- Actors: anonymous user, signed-in user, another tenant, a partner webhook, a background worker, an agent with repo access, a revoked device.
- Assets: accounts, tokens, stored personal data, payments, entitlements, pairing or device-control rights.
- Boundaries: client to API, tenant to tenant, webhook sender to handler, app to operating system, extension to app, build system to release.

Use STRIDE only as a prompt list (spoofing, tampering, repudiation, information disclosure, denial of service, elevation of privilege). Do not turn the list into findings.

## How to substantiate a finding

A confirmed finding names: actor, input they control, control that should stop them, boundary crossed, resource, and concrete result.

Two evidence types are enough:

- `confirmed-repro` — a command in an isolated local harness reproduced the result.
- `confirmed-static` — a reader can follow a path through the code or config even if you could not execute it here (missing toolchain, needs a real device, would require live billing). Write the path as: entry point → controlled input → missing or weak check → resource → impact, with file references.

Do not drop a security finding only because it is not mechanically executable in this environment. Do not upgrade a guess to `confirmed-static` without a path a reviewer can open.

Authorized local defensive tests (invalid signature, stale timestamp, swapped fixture ids) are in scope. Live or shared-system probing is not.

## Object-level authorization

Broken object-level authorization (BOLA, also called IDOR) is the usual API failure: the user is allowed to call the endpoint, then they change an object id and reach someone else's record.

OWASP API1:2023 says every endpoint that takes an object id and acts on that object must check that the signed-in user may perform that action on that object. Comparing a session user id to a `userId` field in the path is not enough for shared or nested resources. Unpredictable ids (UUIDs) are defense in depth. They do not replace the check. Write tests that swap ids across two users and expect denial. Do not ship a change that makes those tests fail.

Tenant isolation is the same idea at account boundaries. Scope every query and every storage key by tenant. A missing `WHERE tenant_id = ?` is a confirmed finding when you can show one tenant's credentials reading another tenant's row, either by running it locally or by tracing the query with no tenant predicate.

### Recipe: object-id swap

- **Prerequisites:** two fixture users (A and B), one object owned by B, a way to authenticate as A in the project's test harness. No production data.
- **Input:** authenticated as A, request B's id on list, read, update, and delete (path, query, body, or GraphQL variable).
- **Expected fail:** A receives B's data or changes B's object (usually 200 with foreign fields).
- **Expected pass:** denial (403 or a 404 that does not leak existence if that is the product rule) and no store change.
- **Artifact:** a test command and output, or a static path from the handler to the query with no owner/tenant check. In implement mode, the test file in the repo.
- **ROI / stop:** worth it for every in-scope endpoint that takes an object id. Stop when list/read/update/delete are covered for each object type, or marked not applicable.

## Sessions and tokens

Check how sessions are created, stored, rotated, and revoked. Treat invite links, magic links, device-pairing codes, and deep links as bearer secrets. Look for tokens in URLs, logs, and crash reports without printing the secret values you find.

## Webhooks

Treat a webhook URL as a public endpoint.

Stripe's docs (and most providers) say: verify the signature over the raw body, reject stale timestamps, deduplicate events, and return `2xx` before slow business work so the provider does not time out and retry. They also retry on non-`2xx` and stop retrying after a `2xx`.

That combination is unsafe if you acknowledge *before* the event is durably stored. A crash after `2xx` and before an in-memory queue write loses the event: the provider thinks delivery succeeded.

Required order:

1. Read the raw body. Do not parse JSON first if the signature covers those exact bytes.
2. Verify the signature (HMAC or the provider's official helper) with a constant-time compare.
3. Reject timestamps outside a small window. Stripe's libraries default to five minutes. A tolerance of `0` disables the recency check; do not do that.
4. Persist or enqueue the event durably (inbox row, durable queue, or equivalent), keyed by event id so duplicates collapse. Commit that write.
5. Return `2xx` only after that durable write succeeds. If the write fails, return `5xx` so the provider retries.
6. Do slow work (fulfillment, email, accounting) in a worker. That worker must be idempotent: one event id produces one fulfillment.
7. Already-stored duplicates still return `2xx` (do not keep the provider retrying work you have).

Provider notes that matter in tests: Stripe does not guarantee delivery order; live-mode automatic retries can last up to three days (sandbox retries are fewer and shorter); each retry gets a new signature and timestamp, so dedupe by event id, not by signature; do not treat `created` as a unique delivery key.

Do not act on an unsigned payload "to make local testing easier" in the shipped handler. Local tests should use a test signing secret and fixture bodies.

### Recipe: webhook authenticity, replay, and durable ack

- **Prerequisites:** handler mounted in a local test server or unit harness, test signing secret, a fixture raw body and valid signature header, a durable inbox you can inspect.
- **Input:** (a) valid signed event; (b) invalid signature; (c) valid signature with a stale timestamp; (d) the same event id delivered twice; (e) simulated persist failure.
- **Expected fail:** (b) or (c) fulfills; (d) fulfills twice; (a) returns `2xx` before any durable write (a later crash would drop the event); (e) still returns `2xx`.
- **Expected pass:** (a) inbox row exists, then `2xx`, then exactly one fulfillment; (b)(c) no fulfillment, non-`2xx` or a documented reject; (d) `2xx` and still one fulfillment; (e) `5xx` and no ack.
- **Artifact:** test output plus the inbox row or queue message id. Proposed or added tests live as described in the skill entrypoint.
- **ROI / stop:** worth it on every reachable webhook. Stop when invalid signature, stale timestamp, duplicate id, persist-then-ack, and persist-failure cases exist.

## Secrets, supply chain, defaults

- No credentials in the tree, in sample env files that are actually loaded, or in CI logs. Note presence; do not paste values into the report.
- Pin GitHub Actions to full commit SHAs. Be careful with `pull_request_target` that checks out untrusted code.
- Do not fetch install scripts over HTTPS and pipe them to a shell as part of a release.
- Secure defaults: deny by default, fail closed, encrypt personal data at rest on devices (see MASVS-STORAGE), and keep debug endpoints out of release builds.

## Mobile

For a mobile app, walk the OWASP MASVS groups that apply: storage, crypto, auth, network, platform interaction, code quality, resilience if the threat model requires it, and privacy. Use MASVS as the control list and the MASTG for how to test a control. Resilience (tamper detection) is often overkill for a straightforward consumer app and worth it when the app's value depends on not being patched.

Family Controls, Screen Time, and similar Apple entitlements: see `06-apple-design-perf.md`. Tokens that identify other apps are opaque and must stay opaque.

## What is not a finding

Generic "add rate limiting," "add more validation," or "a theoretical race" without a reachable case. Missing HTTPS in a sample note. A scanner hit with no path from an entry point. DoS through resource use unless you can show the trigger.

## Stop

You can leave this phase when every in-scope boundary has a written actor and a yes/no on object-level checks, webhook authenticity (including persist-before-ack), and secret handling, or a stated reason it does not apply.
