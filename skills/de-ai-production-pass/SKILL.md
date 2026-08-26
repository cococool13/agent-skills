---
name: de-ai-production-pass
description: "Use when an existing website needs a final production, handoff, or de-AI quality pass before release. Not for prose editing (no-ai-slop), code deslop (ai-slop-cleaner), or watermark stripping (remove-ai-marks)."

---

# De-AI Production Pass

The recurring "make it real and sellable" pass for client work (Coastal
Hardware, Coastal PharmaCare, Spiral, print/signage packages, etc.). Cohen
pitches these as paid engagements, so the bar is a polished, human-looking,
production product.
**Verify everything — never skip a check because "it probably works."**

**Branches:** websites run all four sections; non-web artifacts (print PDFs,
docs, decks) run sections 1 and 4 only.

## 1. De-AI audit (make it not look AI-generated)
- Kill generic AI tells: uniform card grids, emoji bullets (or any emoji in
  print artifacts), letter-spaced ALL-CAPS eyebrow labels, decorative
  alternating accent colors, "Lorem"/placeholder copy, purple-gradient hero
  clichés, centered everything, stocky filler text.
- Use the real brand: keep and **enhance** the existing logo and photos (sharpen
  same images — do NOT replace them with new/generated ones).
- Restore the original/intended fonts; vary rhythm, spacing, and section layouts
  so it reads hand-designed. Real business info stays; only layout/feel improves.
- Done when every tell above is either fixed or confirmed absent — not when the
  surface "looks better."

## 2. Production hardening (run every check, verify output)
- Upgrade dependencies to latest stable; remove dead files and legacy visual
  artifacts; keep the bundle genuinely lightweight.
- Lighthouse/perf: image optimization (correct sizes, lazy, modern formats),
  no layout shift, fast LCP. Accessibility: contrast, alt text, keyboard, focus.
- Responsive verification at 380 / 768 / 1280 via `ego-browser` (screenshots
  desktop + mobile). Fix horizontal overflow and motion issues on mobile.
- SEO/meta: title, description, OG tags, favicon, sitemap.
- Hero check: the **company name** (not the tagline) is the unmistakable focus.

## 3. Real content swap
Replace placeholders with real client details when given (e.g. phone, email,
pricing). Make precise, surgical edits — change only what was specified, keep
everything else (a recurring correction: "keep X, only change Y").

## 4. Handoff
Preserve originals (`_archive/`) before replacing deliverables. Commit per step
where there's a repo. Write `CHANGES.md` documenting what changed. Websites:
deploy to Vercel and use the `code-review` skill before final deploy. Finish
with a short list of what Cohen must still do himself (domain, env vars, print
specs, any content he needs to supply).
