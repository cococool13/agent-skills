---
name: landing-page-design
description: "Use when creating or revising a landing page, marketing site, or conversion section."

---
# Landing Page Design

A landing page is not a homepage. A homepage serves multiple intents. A landing page wins one intent:

**one offer → one audience → one primary action.**

This skill has two halves. **Part A** decides what the page says and how it is structured. **Part B** applies the project’s visual system and verification requirements. Work through A before touching B.

## Scope

Landing pages, marketing sites, and conversion-focused web sections only. Product UI, dashboards, and general components belong to `impeccable` / `premium-web-build` / project design rules. When the user's explicit prompt conflicts with a rule here, the user wins.

**Existing sites.** Preserve the accepted composition and make the requested changes. Use `impeccable` for focused craft work; use `de-ai-production-pass` only when Cohen requests that pass.


**Part B (visual system):** load `references/visual-system.md` only after Part A strategy is set.

---

# PART A — Strategy and structure

## A1. Intake

Infer these from the brief and project docs first. Ask only when missing information changes correctness, scope, or a material product decision; continue independent work while waiting.

**Purpose**
- What is the ONE primary action? (trial, demo, buy, waitlist, download)
- What is the offer, exactly what do they get?
- What counts as a conversion? (click, signup, purchase)

**Audience and context**
- Who is the ICP?
- What problem are they trying to solve?
- Top three objections, meaning why they do not convert today
- Traffic source: ads, search, social, email
- What do visitors already know when they land?

**Proof and assets**
- Proof points: logos, testimonials, numbers, case studies
- Screenshots, demo video, product GIFs
- Guarantees, refund terms, cancellation terms

**Constraints**
- Brand voice: casual or professional
- Design direction: minimal editorial, playful 3D, glass UI
- Mobile priority?

If the user cannot answer, make a reasonable assumption, state it in one line, and continue. Do not stall the build.

## A2. Page structure

Use the sections the offer needs. Preserve an existing approved structure; a small page may need only the hero and essential details.

**Above the fold**
1. Headline, outcome plus audience
2. Subheadline, clarifies how and adds specificity
3. Primary CTA, clear verb plus what they get
4. Verified proof, when available; omit unsupported trust signals
5. Hero visual, product screenshot or video, or a strong illustration

**Mid page (the argument)**
6. Problem to solution, one section
7. Benefits, three to five, outcome driven
8. How it works, three steps
9. Social proof, testimonials or a case study

**Bottom (objection handling)**
10. FAQ covering real objections, when useful
11. Risk reversal, trial, cancel anytime, guarantee
12. Final CTA, identical to the top

If the brief allows a tagline reveal, use B11 somewhere in the mid page argument, typically right after the hero or after benefits.

## A3. Layout selection

Pick one and say why.

| Type | Use when |
|---|---|
| **A. Classic hero plus sections** | The product is understandable from a hero screenshot. Most common. |
| **B. Long form story** | You need to educate and overcome skepticism. |
| **C. Minimal conversion page** | High intent traffic (email to known users), or a short offer like a download or waitlist. |
| **D. Comparison page** | Search intent includes alternatives ("X vs Y", "best for"). Usually paired with SEO pages. |

## A4. Conversion rules

**Match message to source.** If traffic comes from ads, mirror the ad headline in the hero and keep the same promise and visual tone.

**Make the next step obvious.** One primary CTA. Never place competing CTAs above the fold.

**Write benefit first.** Features are what it does. Benefits are what that means for them.

**Be specific.**
- ❌ "Save time and streamline"
- ✅ "Cut your weekly reporting from 4 hours to 15 minutes" — only with evidence for that measured claim

**Reduce uncertainty.** Explain actual price, access, cancellation, and support terms. Mention trials or guarantees only when the product offers them; do not invent an offer.

**Treat objections as a section, not a footnote.** Move the FAQ earlier for high friction offers. Put proof directly beside the claim it supports.

## A5. Copywriting

**Headline formulas**
- "{Outcome} without {pain}"
- "The {category} for {audience}"
- "Ship {result} in {time}"

**Subheadline.** One or two sentences. Clarify what it is and who it is for.

**CTA.** Verb plus what they get. Never "Learn more" or "Submit". Use "Start free trial", "Book a demo", "Get the checklist".

**Benefit bullets.** Bold benefit, then the proof or detail. Example: **Faster iteration** — generate three layout variants in one click.

Follow B1 and the project’s approved voice. Check line breaks in the rendered layout.

## A6. Build order

Work on the agreed sections in dependency order. A typical new page is:

1. Hero
2. Benefits
3. How it works
4. Proof
5. FAQ
6. Final CTA

Never rebuild the whole page on each iteration. Section by section keeps control and keeps diffs reviewable.

## A7. SEO and AEO

**Do not index** ad only campaign pages or highly time bound offers. Use `noindex` or keep them behind a non indexed path.

**Do index** evergreen offers and pages where search intent matches the promise. Add a clear title and meta description, internal links from the homepage and feature pages, and the FAQ in plain question and answer form for AEO. Add FAQ schema if appropriate.

## A8. Pitfalls

- Too many CTAs above the fold
- Vague value prop: "streamline", "optimize"
- A large feature list with no outcomes
- Proof buried at the bottom
- Mobile layout that breaks readability
- No clear next step

---
