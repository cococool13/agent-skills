---
name: scroll-motion-debug
description: "Use when diagnosing or fixing scroll-animation, pinning, layout, or section-transition bugs."

---

# Scroll / Motion Debugging

These bugs recurred painfully (e.g. the "premium is the point" section duplicating
with dead black space before the footer, across multiple Spiral sessions). Random
patches made it worse each time. **Debug systematically — find the cause before
touching CSS.**

## Method (don't guess-and-patch)
1. **Reproduce precisely** with `ego-browser`: full-page screenshot at 1280
   and 380, scroll to the exact glitch, capture before/after. Read the actual DOM
   and computed styles at the broken node — don't infer from the source.
2. **Find the real cause** before editing. Usual suspects:
   - **Pin spacer height** — ScrollTrigger `pin: true` injects a `pin-spacer`;
     leftover/incorrect spacer height is the #1 cause of "dead black space."
   - **Duplicate render** — a section appearing twice is usually a pinned element
     not un-pinning, a cloned node for the pin, or an end-trigger overlap.
   - **Stale measurements** — animations built before fonts/images load, or
     before Lenis is wired, give wrong offsets. Call `ScrollTrigger.refresh()`
     after load, after font ready, and on resize.
   - **Lenis ↔ ScrollTrigger desync** — ensure `scrollerProxy`/`lenis.on('scroll',
     ScrollTrigger.update)` is wired and you render off the single `gsap.ticker`.
3. **Fix the cause, then verify** the fix didn't shift neighbors. Re-screenshot
   the whole page top-to-bottom; check the section ABOVE and BELOW the change.

## Section-to-footer transitions
For the recurring footer-gap problem: confirm the last pinned section's
`end`/spacer resolves exactly at the footer top (no gap, no overlap), then design
the transition deliberately (scrim, mask, or scroll-driven reveal) rather than
nudging margins. After any change, verify at 380/768/1280 — fixes that work on
desktop often reopen the gap on mobile.

## Guardrail
State the diagnosed root cause out loud before editing, and after the fix confirm
with a screenshot. If two attempts don't converge, stop and report findings
rather than continuing to patch (this is exactly where past sessions spiraled).


## Named-bug playbook: "premium is the point" duplicates + dead space before footer
This exact bug recurred across spiral-brief and Spiral-Demo-Site and got *worse*
under random patching ("now there is just a lot of black space" → "flashes again
next to the footer" → "the glowing helix lines are all over the place"). Stop
nudging margins. Work it in this fixed order:

1. **Confirm it's a pin-clone, not a real duplicate.** ScrollTrigger `pin:true`
   on the "premium" section injects a `.pin-spacer` and can leave the pinned node
   rendered at its end position. Inspect the DOM: is the section literally in the
   tree twice, or is one a leftover pinned layer / pin-spacer? Fix the actual one.
2. **Audit the pin lifecycle.** Check `pin`, `pinSpacing`, `end`, and
   `endTrigger` on that section's ScrollTrigger. Dead black space = pin-spacer
   height not collapsing; second-render = element not returning to flow after
   unpin (often `pinSpacing:false` misuse or an `end` that overshoots the footer).
3. **Fix refresh ordering, not symptoms.** Build triggers AFTER fonts + images
   load and AFTER Lenis is wired; call `ScrollTrigger.refresh()` on load, on
   `document.fonts.ready`, and on resize. Stale offsets are why the gap "comes
   back on mobile" after a desktop fix.
4. **Design the footer handoff once.** The last pinned section's resolved `end`
   must equal the footer top — no gap, no overlap. Then add a deliberate
   transition (scrim/mask/scroll reveal). Do not create margin to hide a gap.
5. **Verification gate (mandatory).** Screenshot top-to-bottom at 380/768/1280
   BEFORE and AFTER, and diff the region around the section→footer seam. If the
   second render or black space appears at ANY breakpoint, it is NOT fixed.
   After two non-converging attempts, stop and report the diagnosed cause —
   continuing to patch is exactly what spiraled before.
