---
name: refero-design
description: "Use when researching or designing UI from real app references before implementing."

---
# Refero Design

Progressive disclosure: use this root for scope and non-negotiables, then open
only the reference you need under `references/` (typography, motion, MCP tools,
anti-AI-slop, craft details, example workflow, visual workflow, icons).


| Deep topic | File |
| --- | --- |
| Research workflow | `references/research-workflow.md` |
| Research depth | `references/research-depth.md` |
| Synthesis | `references/synthesis.md` |
| Present findings | `references/present-findings.md` |
| Design craft | `references/design-craft.md` |
| Quality gate | `references/quality-gate.md` |
| Example | `references/example.md` |
| MCP tools / typography / motion / etc. | existing `references/*.md` |


Refero gives agents taste and product evidence. Use it before design work instead of
relying on generic model knowledge.

Refero has three research layers:

1. **Styles** - visual direction and taste.
2. **Screens** - concrete UI patterns and product-screen decisions.
3. **Flows** - multi-step journey logic.

Best results come from combining layers: visual direction from styles, concrete UI
patterns from screens, and sequencing from flows when the task has multiple steps.

## Non-Negotiables

- **Research before design work.** Every design must be grounded in references before
  implementation. Do not rely on the model's generic design taste.
- **Use styles first for visual work when Refero MCP tools are available.** If tools are
  unavailable, use bundled craft references and keep the same reference-lock workflow.
- **Do not copy one reference.** Study several strong references and synthesize a new
  direction for the user's product.
- **Do not average references into a safe middle.** When references conflict, choose one
  dominant direction and preserve its sharp traits. Secondary references may add narrow
  details only.
- **Do not change token meanings.** If a reference says a color, font, radius, shadow,
  gradient, or component is for a specific role, use it only for that role or omit it.
- **Respect imagery guidance.** If a style depends on photography, illustration, product
  shots, or graphics, preserve the media role. Use real/generated/stock assets when
  available; otherwise create an intentional placeholder with art direction. Do not fake
  complex imagery with weak CSS, text, or decorative boxes.
- **Do not use generic frontend/product design skills as a parallel design authority**
  when this skill is available. Refero is the design methodology; generic design skills
  tend to pull work back toward generic AI design.
- **Research output must be specific.** Name the references, describe concrete choices,
  and explain what will be adapted.
- **No design from vibe memory.** Every major visual, layout, content, or interaction
  decision must trace to Refero research, the user's brief, or a craft reference.
- **Synthesize before implementation.** Turn research into a concept, token direction,
  and concrete decision ledger before drawing or coding.
- **A brief is not a build target.** Before implementation, lock either a user-provided
  visual source, an existing product/design-system target, a selected generated mockup,
  or an explicit reference-locked direction approved for direct build.
- **Use image generation only when it changes the outcome.** Image generation can be slow
  and may not exist in every coding environment. Use it for visual exploration, mockups,
  imagery, illustrations, textures, and difficult assets; skip it for small fixes,
  obvious production edits, or code-native UI work.
- **Validate after building visual work.** Compare the rendered implementation against
  the locked target/reference before handoff. Fix actionable design drift instead of
  treating research as sufficient.

## MCP Setup

This skill is useful on its own as a research-first design methodology and craft reference.
Research is mandatory. Use Refero MCP for live style, screen, and flow research when
available; otherwise research with bundled craft references and any user-provided references.

Typical MCP setup:

Prefer the installed Refero MCP in Cursor when available. Otherwise see `references/mcp-tools.md`.

For full tool details, read [references/mcp-tools.md](references/mcp-tools.md).

## Discovery

Before researching, form a short design brief. Ask only for missing information that
would materially change the result; otherwise make reasonable assumptions and proceed.

Clarify:

- what is being designed
- platform: web, iOS, or both
- audience and technical level
- primary user goal
- desired feeling or brand direction
- business/user objections to overcome
- constraints: existing brand, framework, deadline, accessibility, content
- whether the task needs visual direction, concrete UI patterns, journey logic, or a mix
- whether the task should go directly to code, produce visual options first, or create
  generated assets during implementation

Brief format:

```text
Designing [WHAT] for [WHO] on [PLATFORM].
Goal: [PRIMARY USER GOAL].
Tone: [DESIRED FEELING].
Main objection/risk: [OBJECTION].
Must remember: [HOOK OR DISTINCTIVE IDEA].
Constraints: [CONSTRAINTS].
Research needed: [styles/screens/flows].
Path: [direct build / visual exploration / audit / asset generation].
```

## Workflow Routing

Choose the lightest workflow that can produce a high-quality result.

- **Direct build:** use for small UI fixes, clear production edits, existing design-system
  work, or tasks with a concrete source to match. Research and lock the direction, then code.
- **Visual exploration:** use when the user asks for variants, a new visual language, a
  major redesign, a landing page, or another high-visibility surface with several plausible
  directions. Default to three reference-locked options and ask the user to choose; see
  [references/visual-workflow.md](references/visual-workflow.md).
- **Audit:** use captured screenshots, Refero screens, or flows as evidence before critique.
- **Asset generation:** use generated imagery only when the reference lock requires bitmap
  media that code, icons, or existing assets cannot faithfully provide; see
  [references/visual-workflow.md](references/visual-workflow.md).

## Tool Routing

### Use Styles First For Visual Work

Use `refero_search_styles` when the user asks to design, redesign, improve, polish, or
create anything with a visual component.

A style is a semantic design reference extracted from a real web marketing/product page.
It is not a screenshot and not a component library. Search results give previews; full
style references from `refero_get_style` provide design guidance such as visual thesis,
tokens, typography, layout/composition, section rhythm, spacing, elevation, surfaces,
components, imagery treatment, implementation notes, and do/don't rules.

Current limitation: Refero styles currently cover web marketing/product pages such as
landing pages, pricing pages, product marketing sites, editorial brand sites, and SaaS
websites. They do not currently cover in-app dashboards, auth screens, settings screens,
or iOS app screens as style systems. Still use styles for product UI tasks to establish
visual language, then use screens/flows for product logic.

Use styles for:

- look and feel
- brand direction
- landing pages and marketing pages
- typography, palette, layout, section structure, spacing, radius, elevation, surfaces
- component treatments and sometimes component/code examples
- imagery and product screenshot treatment
- design-system inspiration
- making a generic interface feel more tasteful

### Use Screens For Concrete UI Patterns

Use `refero_search_screens` when you need:

- a specific screen type
- a specific component or UI pattern
- page layout and content hierarchy
- copy and CTA patterns
- form/state examples
- dashboards, settings, modals, tables, pricing, empty states, auth, or product-screen details

After finding strong screens:

- use `refero_get_screen` for full details
- use `refero_get_similar_screens` to expand from a strong example
- use `refero_get_screen_image` only when raw screenshot inspection is needed

### Use Flows For Journeys

Use `refero_search_flows` when the task has a before/after sequence:

- onboarding
- signup
- checkout
- subscription management
- cancellation
- account deletion
- password reset
- profile/settings changes
- any multi-step process

After finding a strong flow, use `refero_get_flow` for step-by-step goals, actions,
system responses, and completion states.

### Use Visual Workflow For Images And QA

For image generation, visual options, generated assets, and visual QA, read
[references/visual-workflow.md](references/visual-workflow.md) when the task needs it.

