---
name: de-ai-production-pass
description: "Use when an existing site needs a final production or de-AI pass before release."

---

# De-AI Production Pass

Final "make it real and sellable" pass for client work. Report each check as fixed or confirmed absent.

**Branches:** websites run all four sections; non-web artifacts (print PDFs, docs, decks) run sections 1 and 4 only.

## 1. De-AI audit

Kill generic AI tells: uniform card grids, emoji bullets, letter-spaced ALL-CAPS eyebrows, decorative alternating accents, placeholder copy, purple-gradient hero clichés, centered-everything, stocky filler. Keep and enhance existing logo/photos — do not replace with generated assets. Restore intended fonts; vary rhythm so it reads hand-designed. Real business info stays.

## 2. Production hardening

- Remove dead files and legacy visual artifacts; keep the bundle light. Upgrade dependencies only when the brief or project `CLAUDE.md` asks.
- Perf/a11y: image sizes/lazy/modern formats, no layout shift, contrast, alt, keyboard, focus.
- Responsive verification at 380 / 768 / 1280 via `ego-browser`.
- SEO/meta: title, description, OG, favicon, sitemap.
- Hero: company name (not tagline) is the focus.

## 3. Real content swap

Replace placeholders with real client details when given. Surgical edits only.

## 4. Handoff

Preserve originals (`_archive/`) before replacing deliverables. Commit when there is a repo. Write `CHANGES.md`. Websites: project `CLAUDE.md` then `deploy-cloudflare`. Optional Grok `/review` before final deploy if there is a PR surface. End with what Cohen must still do (domain, env, print specs, missing content).
