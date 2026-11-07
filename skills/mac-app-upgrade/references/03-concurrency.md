# Concurrency, cancellation, and stale UI

Open for any target that hops threads, uses Swift concurrency, or updates UI from I/O.

## Checks

- UI reads and writes stay on the main actor / main queue. After `await`, the view or window may have disappeared or the user may have selected another document — re-check identity before applying results.
- Tasks are cancelled when the view, document, or window goes away. `Task` in `.task` / `.onAppear` should not outlive the UI it updates.
- No data races on shared mutable stores. Prefer actors or isolation the compiler can see.
- Combine / NotificationCenter observers are tied to a lifetime you can name. Look for retain cycles (`self` in long-lived closures, timers that never invalidate).
- Energy: repeating timers and hot observers pause when the app is hidden if the work is only for UI.
- "Use after await": captured indices, file URLs, or security-scoped bookmarks may be invalid; handle errors rather than crashing.

A sleep() to "fix" a race is not a fix.

If the machine is high-rank (two writers, sync, update install vs launch), risk-rank a formal model. Otherwise types and tests are enough.

### Recipe: cancel an in-flight load

- **Prerequisites:** a feature that loads asynchronously into a window or view.
- **Input:** start the load, then close the window or navigate away before it finishes (test or UI).
- **Expected fail:** a later update writes to the old view, or a warning about publishing from a background thread.
- **Expected pass:** the task cancels; no UI update is applied to a gone view.
- **Artifact:** a regression test when possible.
- **ROI / stop:** each in-scope async UI flow.
