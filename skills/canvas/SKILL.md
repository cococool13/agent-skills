---
name: canvas
description: Use when creating or editing a .canvas.tsx artifact or choosing an interactive artifact format. Route to the active client's supported runtime.
---

# Canvas routing

When the artifact is a visual design, follow `~/.agents/design-refs/DESIGN-PREFS.md`, section "Tools, skills, and when", for the mood, the floor, and the references. This skill only picks the artifact runtime.

Determine the active client before selecting an artifact format. The presence
of another client's installed files does not establish runtime support.

- In Cursor, read its native canvas skill at
  `~/.cursor/skills-cursor/canvas/SKILL.md`. Follow that provider's runtime,
  SDK, location and validation rules. Do not copy the native skill here.
- In Codex, Claude Code or Grok, use artifact tools actually available in
  the current session. Read the corresponding installed host skill when
  available. Do not rename Cursor APIs, import `cursor/canvas`, or promise
  Cursor compilation/preview merely because its SDK exists on this Mac.
- If there is no supported interactive artifact runtime, save a standalone
  HTML artifact with inline data, or Markdown for a report. Link the saved
  deliverable and use the host's available preview/file tools.
- When editing an existing `.canvas.tsx`, preserve its intended host and
  source. Validate with that host's actual tooling; report any unavailable
  runtime rather than claiming the file was compiled.

Use the requested artifact format when the user specifies one. Keep data
and content in one authoritative file; do not create a parallel artifact
solely to satisfy a rule from a different client.
