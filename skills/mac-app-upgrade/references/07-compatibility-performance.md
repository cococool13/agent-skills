# Compatibility and performance

## Versions and architectures

- Compare `LSMinimumSystemVersion` / deployment target / package dest with any advertised marketing number and with Sparkle `sparkle:minimumSystemVersion` if an updater exists (three-part versions in appcasts).
- Architectures: list what the project ships (Apple Silicon, Intel, universal). Sparkle 2.9+ can mark an update `sparkle:hardwareRequirements` of `arm64`. Do not claim a slice you did not see in the binary or archive.
- SDK versus runtime: note known API availability checks (`if #available`, `@available`) around newer calls.

If you cannot run `lipo -info` or inspect an xcarchive here, say `needs Xcode` rather than guessing.

## Instruments and launch (when you can run them)

Measure before/after on the same machine and the same build configuration. Write the comparison; do not cite a single absolute number as truth.

Useful templates when available: Time Profiler (hangs), Allocations / Leaks, Energy Log, App Launch. Look for:

- Main-thread I/O or locks during launch and first window.
- Unbounded caches or observers that grow with use.
- Timers or displays that keep the CPU awake in the menu bar extra while idle.
- Launch work that could wait until first use (permission prompts, network).

If Instruments cannot run, static notes about launch sequences are `needs-validation` unless the code path is obvious (`confirmed-static`).

### Recipe: compare two launches

- **Prerequisites:** two local builds, or one build plus a recorded baseline in the repo.
- **Input:** cold launch to first useful window, same host, same config.
- **Expected fail:** a large regression with no matching code reason, or a menu bar extra that never idles.
- **Expected pass:** times and the Instruments trace (or a reason traces could not run) are written down.
- **Artifact:** numbers in `perf.md` or `evidence.md`.
- **ROI / stop:** launch plus the one interaction users wait on. Do not profile every view in `--standard`.
