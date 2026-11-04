---
name: stack-check
description: Use when checking that Stripe, RevenueCat, PostHog and App Store Connect agree on a product's plans, prices, entitlements and events. Read-only.
---

# Stack check

Read-only. Never create, update, refund, or publish anything. Report what disagrees and propose fixes; apply none without Cohen's yes.

1. Scope: name the product and which services it uses. Read the project `AGENTS.md` for product IDs, entitlement names and event names.
2. Inventory each service:
   - Stripe MCP (read tools only; web and Mac licensing via `~/Projects/licensing`): products, prices, payment links or checkout config, test vs live mode.
   - RevenueCat MCP: products, entitlements, offerings, packages; store state per product.
   - App Store Connect (project `asc` scripts or the `asc` CLI, read-only): subscriptions, IAPs, prices, offers.
   - PostHog MCP: the purchase, trial, paywall and churn events the app sends, their last-seen time and volume.
3. Compare:
   - Every store product maps to one RevenueCat product, which grants the right entitlement through an offering.
   - Prices and trial/offer terms match across Stripe, App Store Connect and in-app copy.
   - Each purchase path fires the expected PostHog event, and recent events exist for live products.
   - Nothing live points to an archived or test product or key.
4. Report one table: item, each service's value, status (match / mismatch / missing), and the proposed fix. List what you could not read.
