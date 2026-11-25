# Mobbin MCP tools

Use the exact tool names. Clients may prefix a namespace; do not invent aliases.

Endpoint: `https://api.mobbin.com/mcp`. Auth: OAuth through the user's Mobbin account. Rate limit: about 60 requests per 60 seconds per user. Image URLs returned by the server may expire; download a `image_url` promptly if you need to save or paste it.

## Search

### `search_screens`

Search individual mobile and web UI screens. Use it for a specific state or pattern: login, paywall, empty state, dialog, form, navigation, settings, or a component treatment.

Keep the query tight and concrete. Example queries:

```text
iOS paywall with a free-trial timeline
empty state for a habit tracker home
settings list with account and billing rows
Android navigation bar with five tabs
web app dialog for discarding unsaved changes
```

### `search_flows`

Search ordered, multi-step user flows. Use it when sequence and context matter: onboarding, checkout, account setup, identity verification, subscription, cancellation, or permission prompts.

```text
iOS onboarding that leads into a paywall
checkout with Apple Pay and an order summary
subscription cancellation with a retention offer
```

### `search_sections`

Search website sections. Use it for page-composition references: heroes, pricing sections, testimonials, navigation, and footers.

```text
pricing section with monthly and annual toggle
hero with a product screenshot and a short headline
footer with legal links and a compact sitemap
```

## Saved

### `list_collections`

List the user's saved collections, including an all-saved view when the server provides one.

### `get_collection_contents`

Read the saved screens, flows, or sections in a collection.

### `create_collection`

Create a collection for a project or mood. Use a clear name (the project, surface, or question).

### `save_content`

Save a screen, flow, or section so it can be reused. Prefer this when a find will be cited in `DIRECTION.md`.

### `add_comment`

Comment on a saved screen, flow, or section (for example, what to take and what to avoid).

## Search discipline

- Run a few precise searches, not a catalogue sweep.
- Stop once you have 3–6 strong references that cover the brief.
- Stay within the rate limit. If a call is refused, wait and narrow the query.
- Synthesize from a few strong references. Keep searches tight.
