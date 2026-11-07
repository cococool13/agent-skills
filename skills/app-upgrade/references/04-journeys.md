# User journeys

For each important flow in `map.md`, fill this matrix. A blank cell is a gap. Write `N/A` with a reason when a column cannot apply (for example, no offline mode and the UI says so).

| Flow | Normal | Error | Cancel | Retry | Offline | Permission denied | Entitlement or paywall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| (name) |  |  |  |  |  |  |  |

Write what the user sees and what the store looks like after each cell, not "it should work."

Drive the cells you can for real: iOS in the simulator (`ios-simulator-skill`, or the MobileBuildMCP / iOS Simulator tools), web views and local servers in a browser (the built-in browser pane or Playwright). Use local builds and fixtures only. A cell you read from code instead of running is labeled `static`; a cell that needs a real device is labeled `device-gap`.

## What to look for

- **Normal.** The happy path, including first run and returning user.
- **Error.** Invalid input, server 4xx/5xx, partial writes, "the other side accepted but we never heard back."
- **Cancel.** The user backs out mid-flow. In-flight requests must be cancelled (structured concurrency: a parent task cancels its children). A cancelled payment or pairing attempt must not complete later without a new user action, unless the product explicitly says it will.
- **Retry.** The same intent sent twice, including a double tap and a client timeout followed by a retry. This is where idempotency keys and recovery points matter. Retrying a POST without a key is how people get double charges.
- **Offline.** Queue, conflict, and resume. If the app claims offline support, say how conflicts resolve. "Last write wins" is a decision, not a default. If there is no offline mode, the UI should say so instead of spinning forever.
- **Permission denied.** The OS prompt, a "don't allow," a later revoke, and restricted settings (notifications, photos, Screen Time, local network). After a revoke, tokens and cached rights must stop working.
- **Entitlement.** Expired subscription, family organizer vs member, refund, billing retry, and "the store says purchased but the app has not unlocked." Do not call live billing to test this. Use store sandbox or recorded fixtures.

SwiftUI `.task` cancels when the view goes away. Unstructured `Task { }` and `Task.detached` do not. If you start work from a view, prefer the structured modifier so leaving the screen cancels the work.

### Recipe: fill a journey cell

- **Prerequisites:** the flow named in `map.md`, any fixtures (two users, an expired entitlement stub, airplane mode).
- **Input:** the user action for that cell (cancel on the confirm step, retry after a client timeout, revoke the OS permission in Settings, and so on).
- **Expected fail:** the UI shows success while the store disagrees, a cancelled request fulfills later, or a retry doubles a side effect.
- **Expected pass:** you can write one sentence for what the user sees and one for what the store contains.
- **Artifact:** a completed cell in `journeys.md`, plus a screenshot or log when the UI changed. Surprising cells become a proposed or added test.
- **ROI / stop:** worth it for every user-critical flow. Stop when each applicable column has a written result. Do not invent an offline CRDT design for an online-only app that already says it is online-only.

## Stop

You can leave this phase when every in-scope flow has a written result for each column that applies, and each surprising cell is either a test, a proposed guard, or a finding.
