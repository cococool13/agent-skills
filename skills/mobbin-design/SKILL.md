---
name: mobbin-design
description: "Use when researching or designing UI from real app and website references before implementing."
---
# Mobbin Design

Use Mobbin before design work instead of relying on generic model taste. It covers iOS, Android, web apps, and website sections.

Mobbin has three research layers:

1. **Screens** (`search_screens`) — a specific state or pattern: login, paywall, empty state, dialog, form, or navigation.
2. **Flows** (`search_flows`) — ordered, multi-step journeys: onboarding, checkout, signup, subscription, cancellation, or account setup.
3. **Sections** (`search_sections`) — website composition: heroes, pricing, testimonials, navigation, and footers.

Saved collections: `list_collections`, `get_collection_contents`, `create_collection`, `save_content`, `add_comment`.

Best results come from combining layers: concrete UI from screens, sequencing from flows, and page composition from sections. Synthesize from a few strong references. Keep searches tight.

Refero is an optional secondary source, prepaid through August 2027. Use it only when Mobbin is missing a needed pattern. Prefer Mobbin whenever it is connected.

## Non-negotiables

- **Research before design work.** Ground every design in named references before implementation.
- **Synthesize from a few strong references.** Study several, then form a direction for the user's product.
- **Do not average references into a safe middle.** When references conflict, choose one dominant direction and preserve its sharp traits. Secondary references may add narrow details only.
- **Research output must be specific.** Name the references, describe concrete choices, and explain what will be adapted.
- **No design from vibe memory.** Every major visual, layout, content, or interaction decision must trace to Mobbin research, the user's brief, or a named craft reference.
- **Synthesize before implementation.** Turn research into a concept, token direction, and concrete decision ledger before drawing or coding.
- **Keep searches tight.** Prefer precise queries and a short list of strong hits over broad paging. Mobbin allows about 60 requests per minute; do not burn the budget on exhaustive sweeps.

## MCP setup

Server: `https://api.mobbin.com/mcp` (Streamable HTTP, OAuth). No API key. On first use the client opens a browser for Mobbin sign-in.

Use the exact tool names: `search_screens`, `search_flows`, `search_sections`, `list_collections`, `get_collection_contents`, `create_collection`, `save_content`, `add_comment`. Clients may namespace them; do not invent other names.

If Mobbin MCP is missing on this host, say so and research from user-provided references, Stacks, and bundled craft. Do not silently fall back to generic model taste.

For tool details, read [references/mcp-tools.md](references/mcp-tools.md). For the research loop, read [references/research-workflow.md](references/research-workflow.md).

## Discovery

Before researching, form a short design brief. Ask only for missing information that would materially change the result; otherwise make reasonable assumptions and proceed.

```text
Designing [WHAT] for [WHO] on [PLATFORM].
Goal: [PRIMARY USER GOAL].
Tone: [DESIRED FEELING].
Main objection/risk: [OBJECTION].
Must remember: [HOOK OR DISTINCTIVE IDEA].
Constraints: [CONSTRAINTS].
Research needed: [screens/flows/sections].
Path: [direct build / visual exploration / audit].
```

Platform may be iOS, Android, web, or a mix. Mobbin covers all three plus website sections.

## Tool routing

- **`search_screens`** for a specific screen type, component, or UI pattern (paywall, empty state, settings, nav, form).
- **`search_flows`** when sequence matters (onboarding, checkout, cancellation, permissions, paywall journey).
- **`search_sections`** for marketing or site composition (hero, pricing, footer, testimonials, nav).
- After a strong hit, use later pages only if the first results are weak. Save useful finds with `save_content` or `create_collection` when the user will want them again.

Settle on 3–6 references. List each in `DIRECTION.md` (or the project's design note) with its link and one line on what you took.
