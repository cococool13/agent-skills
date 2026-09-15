# PART B — Visual system

**Read [`references/visual-system.md`](references/visual-system.md) before writing any
styles, and keep it open while you build.** It holds every binding visual value:

- **B1** typefaces, copy rules, the Tailwind type scale, button type
- **B2** the spacing table · **B3** the nested-radius formula
- **B4** borders and dark-mode backgrounds · **B5** hero heading gradient and 680px caps
- **B6** icon sets · **B7** motion easing, island nav, scroll interpolation
- **B8** content realism · **B9** required states · **B10** ship requirements
- **B11** the optional tagline reveal section

Do not invent a font size, spacing value, radius, colour, or easing curve that is not in
that file. If a value you need is absent, snap to the nearest listed value rather than
introducing a new one.

---

# Output format

When generating a landing page from scratch, return these in order before writing code:

1. **Page outline** — sections and their order
2. **Hero copy** — headline, subheadline, CTA, proof line
3. **Benefits** — three to five outcome driven bullets
4. **How it works** — three steps
5. **FAQ** — six to twelve questions and answers
6. **SEO / AEO** — index or noindex recommendation, plus title and meta if indexed
7. **Layout recommendation** — A, B, C, or D, and why

Then build section by section per A6.

---

# Quick checklist

**Strategy**
- [ ] One offer, one audience, one primary action
- [ ] No competing CTAs above the fold
- [ ] Specific numbers instead of vague verbs
- [ ] At least one risk reversal
- [ ] Proof sits next to the claim it supports
- [ ] Layout type chosen deliberately

**Visual**
- [ ] Single approved typeface, no italics, no ultra bold
- [ ] No hyphens in copy, no orphaned words
- [ ] Every font size lands on a Tailwind scale step
- [ ] Every spacing value comes from the spacing table
- [ ] Nested radii follow the formula
- [ ] No single sided card borders, no background gradients
- [ ] Hero heading and subheading capped at 680px with meaningful line breaks
- [ ] Icons from Phosphor, Solar, or Iconamoon
- [ ] Every transition uses a custom cubic bezier, scroll reveals use IntersectionObserver
- [ ] Tagline reveal section present, minimum two lines, words activate one at a time on scroll

**Content and ship**
- [ ] No Lorem Ipsum, no placeholder brands, no AI cliches, no round fake numbers
- [ ] Hover, active, focus, loading, empty, and error states all present
- [ ] No dead links, current nav item indicated
- [ ] 404, legal links, form validation, favicon, meta tags, alt text
