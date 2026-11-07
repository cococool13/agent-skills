# Reliability and platform configuration

Load only if the inventory found APIs, background jobs, webhooks, file uploads, Workers/edge bindings, or a CMS. Otherwise list this module as not loaded in `map.md` and stop.

## Retries and idempotency

Foreign mutations (billing, email, remote APIs) need an idempotency key or a durable recovery point. Local ACID work can be one transaction; Stripe-like or queue calls cannot. A retry with the same key must not double-charge or double-send. Record seeds and time limits if you simulate.

## Webhooks

Verify over the raw body. Persist or enqueue durably, then return 2xx; return 5xx if persist fails. Process duplicates once. Do not ACK a live provider from this skill.

## Uploads

Authn/authz, size and type checks, malware-safe storage if claimed, accessibility of any user-visible upload UI (labels, errors, progress). Serve with a safe content type. Do not upload real customer files.

## Workers and edge

Read `wrangler.toml` / route tables / bindings that are already in the repo. List secrets as names only. Do not change remote Cloudflare or host config unless implement mode and the user named that change. Do not deploy.

## CMS (including Webflow)

Read schema, collection slugs, and published versus staging configuration available locally. Check that preview and production hosts are not confused in canonicals or robots. Do not publish, unpublish, or rewrite live CMS items unless the user named that action in implement mode.

### Recipe: duplicate webhook delivery (when a webhook exists)

- **Prerequisites:** fixture payload, test secret, local handler or documented test path.
- **Input:** the same event id delivered twice.
- **Expected fail:** two side effects.
- **Expected pass:** one side effect; second call is a safe 2xx after durable dedupe.
- **Artifact:** proposed guard or test in the run folder.
- **ROI / stop:** each webhook type in scope.
