# Accessibility (Mac)

Open for any UI target. Automated accessibility inspectors help; they do not replace a keyboard and VoiceOver pass on the real AppKit/SwiftUI tree (`NSAccessibility` / SwiftUI accessibility modifiers).

## Checks

- Every interactive control has a name, role, and value. Custom drawings expose `accessibilityLabel`, `accessibilityRole`, and actions.
- Full keyboard operation: tab loops (or the documented keyboard set), menu key equivalents, and no trap. Menu bar extras can be reached.
- VoiceOver: order matches visual order; grouped controls are not a soup of unlabeled images.
- Dynamic Type / larger content sizes: layouts flex or clip with a still-usable control.
- Contrast of text and non-text UI on the shipped appearance(s), including dark mode if you ship it.
- `prefers-reduced-motion` / `NSWorkspace.accessibilityDisplayShouldReduceMotion` (or SwiftUI environment): decorative motion stops; necessary state changes remain understandable.
- Window titles and document titles update when the file name changes.

Say which screens were walked manually versus only inspected in code. If you cannot run VoiceOver here, write static notes as `confirmed-static` or `needs-validation`, not as a pass.

### Recipe: VoiceOver title of the primary window

- **Prerequisites:** the main window hierarchy in code or a running debug build you may use.
- **Input:** move VoiceOver (or inspect the accessibility tree) to the primary heading and the primary action.
- **Expected fail:** "button" with no name, or a decorative image in the swipe order.
- **Expected pass:** spoken name matches the visual purpose.
- **Artifact:** notes in `a11y.md` or `evidence.md`.
- **ROI / stop:** each unique window or extra. Stop when the same component repeats.
