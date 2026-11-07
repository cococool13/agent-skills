# Design quality

Open for user-facing pages. Preserve the site's approved brand: typefaces, scale, color, voice, and existing components. Do not "clean up" a distinctive layout into generic cards, even gradients, or interchangeable hero-and-three-up slop.

This module stays first-class. A shorter entrypoint is not permission to skip it.

## What to look at

- **Type:** sizes and line-lengths that match the brand scale; no random third font unless the brand already uses it.
- **Spacing:** consistent rhythm from the existing tokens or observed scale; no one-off magic margins that collide at the breakpoint you checked.
- **Copy:** specific, grammatical, in the site's voice. Remove placeholder, lorem, and "welcome to our website" if the rest of the site does not talk that way.
- **Hierarchy:** one primary action per view; secondary actions quieter.
- **States:** empty, loading, error, success, disabled, and partial data are designed, not default browser chrome dumped on the brand.
- **Imagery:** existing photography or illustration style; do not invent stock scenes that clash.
- **Motion:** short, meaningful, honor `prefers-reduced-motion`.
- **Dark / forced colors:** if the site claims support, check it; if it does not, do not invent a theme.

In implement mode, match tokens and components already in the repo. If there is no design system, copy the nearest existing page rather than introducing a new aesthetic.

### Recipe: compare a page to the brand

- **Prerequisites:** a reference page the owner already ships (home, or a cited style source in the repo).
- **Input:** the in-scope page next to that reference.
- **Expected fail:** new typeface, off-brand color, generic card grid, or placeholder copy on a page that otherwise sounds like a person.
- **Expected pass:** the page could sit next to the reference without looking like a different product.
- **Artifact:** notes in `design.md` or `evidence.md`, with the reference page named.
- **ROI / stop:** in-scope templates. Stop when issues are pattern-level rather than page-unique.
