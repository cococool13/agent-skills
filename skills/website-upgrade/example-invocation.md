# Example invocation

This file is an example only. It is not part of the generic workflow and does not name a real product.

## Prompt

Use the website-upgrade skill in report-only mode, standard depth, on this repo. The property has a public marketing site and may also have a small backend; infer the kind from the tree and do not run API object-authorization tests on static pages.

Do not publish, deploy, submit real forms, or open a pull request. Write the run folder outside the repo.

I want:

1. A kind routing note: which modules you loaded and which you skipped, with reasons.
2. Journeys for the main convert-or-contact path, inspected without sending a live form.
3. A keyboard pass plan against WCAG 2.2 (including focus not obscured by sticky UI) and a small viewport matrix.
4. Design notes that preserve the existing brand rather than suggesting a generic layout.
5. Core Web Vitals discussed as field versus lab, with budgets, not a Lighthouse 100 target.
6. Indexability and structured data only if they match visible content.
7. Security headers for the public site; deeper API checks only if an API exists.

If you cannot use a separate reviewer, label the second look as self-review.

## What good output looks like

`run-meta.json`, `map.md` (kind + modules not loaded), `coverage.md`, `evidence.md`, and `findings.json`. Extra module files only where something was actually checked. No product-code changes in this report-only example.

If a later invocation includes `--implement`, that flag alone is enough to apply local fixes on a new branch, still without publishing.
