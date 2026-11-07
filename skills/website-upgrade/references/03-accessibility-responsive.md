# Accessibility and responsive behavior

Open for any user-facing page. WCAG 2.2 (W3C Recommendation, 5 October 2023) adds nine success criteria beyond 2.1 and removes 4.1.1 Parsing. Automations help; they do not replace keyboard and screen-reader checks.

## Automated versus manual

| Kind | What it can claim | What it cannot |
| --- | --- | --- |
| Automated (axe, Lighthouse a11y, built-in linters) | Missing names, contrast on computed styles, some roles | Whether VoiceOver order makes sense, whether a custom widget is usable |
| Manual keyboard | Tab order, focus visible, no keyboard trap, focus not entirely hidden | Spoken output |
| Manual VoiceOver / screen reader | Name, role, value, live regions | Every OS/browser pairing unless you list them |

Say which tools ran and which journeys were walked by keyboard. A green automated score with no keyboard pass is incomplete, not a pass.

## WCAG 2.2 checks that agents miss

Walk these on in-scope pages, especially beyond 2.1 muscle memory:

- **2.4.11 Focus Not Obscured (Minimum, AA):** focused controls are not entirely hidden by sticky headers, cookie banners, or chat widgets.
- **2.5.7 Dragging Movements (AA):** any drag reorder has a single-pointer alternative.
- **2.5.8 Target Size (Minimum, AA):** targets are at least 24×24 CSS pixels or adequately spaced.
- **3.2.6 Consistent Help (A):** help, chat, or contact repeats in the same relative order when present.
- **3.3.7 Redundant Entry (A):** do not ask for the same information twice in one process unless essential or for security.
- **3.3.8 Accessible Authentication (Minimum, AA):** login must not require transcribing or recalling a puzzle if a password manager or copy-paste cannot complete it. Cognitive function tests need an alternative or an assistive mechanism.

Also check: headings, labels, alt text that is not junk, captions, reduced motion (`prefers-reduced-motion`), text resize, and that decorative images are hidden from AT.

## Responsive, browser, and input matrix

Pick a small matrix that matches the audience, then walk it. Do not invent device lab coverage you did not run.

| Axis | Typical samples | What to note |
| --- | --- | --- |
| Viewport | a narrow phone width, a tablet width, the site's desktop breakpoint | Overflow, sticky bars covering focus, sticky CTA collisions |
| Input | keyboard, pointer, coarse touch | 24px targets, hover-only actions |
| Browser | the documented support list, or current Safari/Chrome/Firefox if none is documented | Prefix gaps, date inputs, dialogs |
| Motion / contrast | reduced motion, increased contrast if you ship it | Animation that cannot be stopped |

### Recipe: keyboard pass of one journey

- **Prerequisites:** a local or preview URL you are allowed to open; a host browser adapter if you need one.
- **Input:** Tab/Shift+Tab from the first to the last interactive control of the journey, then activate the primary action without a mouse.
- **Expected fail:** a trap, an invisible focus, a control hidden behind a banner (2.4.11), or an action that cannot be reached.
- **Expected pass:** visible focus throughout; all actions reachable; order matches the reading order.
- **Artifact:** notes in `a11y.md` or `evidence.md`.
- **ROI / stop:** every in-scope converting journey. Stop when patterns repeat.
