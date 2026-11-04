---
name: preship-four-personas
description: "Use before shipping any customer-facing surface (landing, pricing, feature announcement, ad, launch email, onboarding copy, App Store or marketing site, Workers/Pages site): a review-only Customer / Competitor / Skeptic / Conversion pass on messaging and positioning. Runs next to launch-qa-five-personas (Roundtable); both must pass."
---

# Pre-ship 4-persona review

Roundtable (`launch-qa-five-personas`) owns live browser UX on the preview or live URL. This skill owns messaging and positioning. Both must return PASS/SHIP with no blockers before ship. Review only: never edit, deploy, push, or submit.


Goal: review one customer-facing artifact (landing, feature, ad, email, onboarding, App Store / marketing copy, or Workers/Pages site) for Cohen's iOS/Mac apps and Cloudflare Workers sites. Return findings that would change the ship. Do not rewrite the whole thing. Do not edit code, deploy, push, submit, or loosen tests. Gates run locally (GitHub-hosted CI is blocked).

Inputs (state what you used): the artifact (URL, file path, or pasted copy), who it's for (ICP in one line), and the one success action.

## Personas (same artifact, four passes)

1. CUSTOMER — Be the exact buyer. Flag confusion, irrelevance, claims you'd doubt, and what would make you leave. Check that the promise matches what the app/site actually does.
2. COMPETITOR — Work for the strongest rival. Flag weak spots, easy attacks, copyable positioning, and lines that sound like every other AI/productivity app.
3. SKEPTIC — Every claim needs proof. Flag vague, exaggerated, or unsupported lines; missing privacy/terms/renewal/price evidence; numbers or testimonials with no source.
4. CONVERSION — Top to bottom. Flag every place someone must stop, think, search for context, or guess the next click (CTA clarity, pricing→checkout/TestFlight path, Workers preview vs production mismatch).

## Output

1. Verdict first line: SHIP or BLOCK.
2. Findings table, sorted by severity then impact:

| # | Severity | Persona(s) | Finding | Change (where + what) | Why | Evidence |
|---|----------|------------|---------|----------------------|-----|----------|

Severity: Blocker (can't trust / can't act / missing legal or price proof) · Major (real friction or weak claim) · Nit (polish).
Evidence required: `file:line`, a local command + its output, or a screenshot path. No invented metrics.
3. Top 5 changes only (combine the four passes). Exact where + what + why. Not a full rewrite.
4. Not run: any check you couldn't do, and why.

## Done when

- All four personas ran on the same artifact.
- Every finding has severity + evidence.
- Top 5 changes listed; verdict is SHIP (no blockers) or BLOCK (name the blockers).
- Nothing was edited, deployed, pushed, or submitted.
