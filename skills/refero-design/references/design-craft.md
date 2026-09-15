## Design Craft

After research, execute like a senior product designer. Use the bundled references only
when relevant; do not load every file by default.

- Typography: [references/typography.md](references/typography.md)
- Color: [references/color.md](references/color.md)
- Motion: [references/motion.md](references/motion.md)
- Icons: [references/icons.md](references/icons.md)
- Forms, focus, images, touch, performance, accessibility: [references/craft-details.md](references/craft-details.md)
- Copywriting and persuasion: [references/copywriting.md](references/copywriting.md)
- Anti-AI-slop checks: [references/anti-ai-slop.md](references/anti-ai-slop.md)

Core craft rules:

- Define tokens before implementation: type scale, colors, spacing, radius, shadows.
- Preserve the primary reference's strongest traits instead of normalizing them.
- Preserve token roles from references. Do not turn a CTA accent into a background, a
  code-only color into UI chrome, or a decorative gradient into an interface surface.
- Preserve imagery roles from references. Use capable assets when available; otherwise
  prefer an honest, well-sized placeholder over a poor fake illustration or photo.
- Use brand-appropriate colors from research. Do not default to indigo/violet unless the
  user explicitly asks for it.
- Treat "calm editorial" as a current AI-slop risk. Do not default to decorative headline
  word swaps: one word or short phrase set in a different display/serif/script/italic
  style or accent color, warm ivory/cream canvases, or olive/clay/terracotta palettes unless
  research and product context justify them.
- Avoid generic hero -> features grid -> pricing -> FAQ -> CTA unless research supports it.
- Use real product evidence for copy, trust signals, objection handling, and section order.
- Create at least one memorable detail: a visual move, interaction, layout choice, or copy
  detail users would remember.
- Balance headings and short display text with `text-wrap: balance`; use `text-wrap: pretty`
  selectively for prose. Check key breakpoints for orphan words and awkward final lines.
- Keep accessibility and responsive behavior in the design, not as a late pass.
