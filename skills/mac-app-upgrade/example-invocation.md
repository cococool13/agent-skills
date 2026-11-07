# Example invocation

This file is an example only. It is not part of the generic workflow and does not name a real product.

## Prompt

Use the mac-app-upgrade skill in report-only mode, standard depth, on this Mac app checkout. Infer whether it ships as a Developer ID notarized download or a Mac App Store build from the project; do not assume App Sandbox.

Do not submit notarization, staple a ticket, publish an appcast, run `tccutil reset`, or open a pull request. Write the run folder outside the repo. Use temporary directories for any file fixtures — not the real user Library.

I want:

1. Kind and distribution inference, with the signals you used.
2. Lifecycle notes for windows (and the menu bar extra if one exists), including sleep/wake or display changes when relevant.
3. Concurrency: main-actor use and what happens if a window closes while a task is in flight.
4. Persistence and permission denial paths for features the app actually uses.
5. Keyboard and VoiceOver notes; if VoiceOver cannot run here, say so.
6. Read-only validation of any existing signed artifact (`codesign`, `spctl`, `stapler validate` as available).
7. If Sparkle is present, check EdDSA appcast signatures as separate from Apple code signing, and that private keys are not in the tree. Do not print key material.

If you cannot use a separate reviewer, label the second look as self-review.

## What good output looks like

`run-meta.json`, `map.md` (kind, distribution, modules not loaded), `coverage.md`, `evidence.md`, and `findings.json`. No Sparkle stubs if there is no updater. No product-code changes in this report-only example.

If a later invocation includes `--implement`, that flag alone is enough to apply local fixes on a new branch, still without shipping or notarizing.
