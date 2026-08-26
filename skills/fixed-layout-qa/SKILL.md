---
name: fixed-layout-qa
description: "Use when creating, revising, or verifying a PDF, slide deck, brochure, report, or other fixed-layout deliverable."

---

# Fixed Layout QA

## Establish the artifact boundary

1. Identify the editable source, generated output, intended delivery format, and required page or slide count. Preserve the original unless the user explicitly authorizes replacement.
2. Read the nearest project instructions and existing design/brand material. Treat print size, page order, and required wording as constraints.
3. For DOCX, PDF, spreadsheet, or slide work, load the workspace document dependencies before selecting a tool. Reuse the project's existing render/build path when available.

## Audit through rendered evidence

Render every page or slide at a useful inspection size. Check each for:

- clipped, overlapping, or off-canvas content;
- missing, stretched, low-resolution, or incorrectly layered assets;
- unreadable type, poor contrast, broken hierarchy, and inconsistent spacing;
- unexpected blank pages, duplicate content, wrong page order, or format drift;
- print-specific issues such as margins, bleed, pagination, and page breaks.

Inspect representative dense, image-heavy, and final pages in detail; do not infer a whole-file result from the cover or first page.

## Make changes safely

- Keep the source and delivered artifact synchronized when both are in scope.
- Make only requested content changes. Preserve names, dates, figures, quotations, and legal language exactly unless the user authorizes a correction.
- When a visual change could alter meaning or legal accuracy, stop and ask rather than guessing.
- Re-render all affected pages or slides after changes; recheck adjacent pages when pagination or layout can shift.

## Completion evidence

Report the rendered page/slide count, what was checked, fixed defects with page references, and remaining limitations. Do not call the artifact ready until all pages/slides render successfully and the final visual pass finds no unresolved clipping, missing assets, or readability defects.

## Boundaries

- For a live frontend, use `impeccable` or the project's browser QA workflow.
- For PDF manipulation without a full artifact review, use `pdf`.
- For text-only revision, use the appropriate writing workflow, then return here before final delivery when layout matters.
