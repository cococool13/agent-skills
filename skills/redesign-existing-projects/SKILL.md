---
name: redesign-existing-projects
description: "Use when an existing website or app needs a visual, UX, or implementation-quality redesign."

---

# Redesign Existing Projects

This skill is a **diagnostic**. It finds what is wrong with an existing interface and fixes it in place.

Two reference files carry the detail: `references/audit-checklist.md` tells you *what to
look for*, `references/design-values.md` tells you *what to replace it with*. Read both.
To adapt this skill to a different design system, edit only `design-values.md` — the whole
audit follows it automatically.

## How this works

1. **Scan** — Read the codebase. Identify the framework, styling method (Tailwind, vanilla CSS, styled-components, CSS modules), and the current design patterns.
2. **Diagnose** — Run the full audit below. List every generic pattern, weak point, and missing state you find. Report before fixing.
3. **Fix** — Apply targeted upgrades inside the existing stack, in the Fix Priority order. Do not rewrite from scratch. Improve what is there.

---

# Design audit

**Read [`references/audit-checklist.md`](references/audit-checklist.md) and work through
every section before proposing any change.** It covers typography, colour and surfaces,
layout, interactivity and states, content, component patterns, iconography, code quality,
and strategic omissions.

The audit is only complete when every one of those nine areas has a verdict — a finding
with `file:line`, or an explicit "no issues found". A section you skipped is not a section
that passed.

# Upgrade techniques

High impact replacements to pull from once the audit fixes are in.

**Typography**
- Variable font animation, interpolating weight or width on scroll or hover
- Outlined to filled text transitions on scroll entry
- Text mask reveals, with large type acting as a window onto video or imagery

**Layout**
- Broken grid and deliberate asymmetry, with elements overlapping or bleeding off screen
- Whitespace maximization to force focus onto one element
- Parallax card stacks that stick and pile during scroll
- Split screen scroll with halves moving in opposite directions

**Motion**
- Smooth scroll with inertia, decoupled from browser defaults
- Staggered entry, never mounting everything at once
- Spring physics on all interactive elements
- Scroll driven reveals through expanding masks, wipes, or draw on SVG paths

**Surfaces**
- True glassmorphism: `backdrop-filter` plus a 1px inner border and a subtle inner shadow to simulate edge refraction
- Spotlight borders that illuminate under the cursor
- Fixed, `pointer-events: none` grain overlays to break digital flatness
- Colored, tinted shadows carrying the background hue

Note: none of these may reintroduce a background gradient. Depth comes from noise, imagery, shadow, and layering.

---

# Fix priority

Maximum visual impact, minimum risk, in this order:

1. **Font swap** — biggest instant improvement, lowest risk
2. **Color and surface cleanup** — snap to the approved palette, remove background gradients
3. **Hover, active, and focus states** — makes the interface feel alive
4. **Layout and spacing** — grid, max width, spacing scale, nested radius formula
5. **Motion pass** — custom easing curves, scroll reveals via IntersectionObserver, island nav
6. **Replace generic components** — swap cliche patterns for the alternatives above
7. **Loading, empty, and error states** — makes it feel finished
8. **Copy pass** — remove cliches, add specificity, fix CTAs
9. **Type scale polish** — the premium final touch

---

# Rules

- Work with the existing tech stack. Do not migrate frameworks or styling libraries.
- Do not break existing functionality. Test after every change.
- Report the diagnosis before applying fixes. Let the user veto items.
- Check the project's dependency file before importing any new library.
- If the project uses Tailwind, check the version, v3 or v4, before touching config.
- If there is no framework, use vanilla CSS.
- Keep changes reviewable and focused. Small targeted improvements over big rewrites.
- Never invent a design value. If it is not in Design Values, ask.

---

# Design values

**Read [`references/design-values.md`](references/design-values.md) before replacing any
value.** It is the single source of truth for fonts, dark backgrounds, the hero gradient,
spacing, radius, icons, motion, and the type scale.

Never invent a font, hex value, spacing number, radius, or easing curve that is not in that
file. If a situation is not covered there, ask rather than guessing.
