# Lifecycle, windows, and system UI

Open for every Mac UI target. Extra rows below apply only when inventory found a menu bar extra, document type, helper, or multi-display behavior.

## Lifecycle and identity

- Launch, resign active, background, hide, terminate, and sudden termination: work is saved or explicitly discardable.
- SwiftUI: `scenePhase`, window placement, and `defaultAppStorage` / scene storage do not leak the wrong window's state.
- AppKit: window restoration identifiers match windows; first responder after open is sensible.
- Navigation: the back path and the deep URL or user activity restore the same document or pane.
- Document identity: two windows on the same file share one document object; Save / Duplicate / Rename / Move do not silently fork state. Dirty markers match unsaved changes.

## Menu bar extras

If `LSUIElement` or a status item exists:

- Left/right click, keyboard navigation of the menu, and "Open main window" if advertised.
- The extra does not steal key focus unexpectedly.
- Menu titles stay under a reasonable width; remaining items still work.

## Multi-display, sleep, space, and login

Walk these when the app cares about screens or session:

- Moving the window or status item across displays, including a display being unplugged (`NSApplication.didChangeScreenParametersNotification` or SwiftUI equivalents).
- Sleep / wake: timers, streams, and file coordinators resume without duplicate work or a stuck "connecting" state.
- Login items / `SMAppService` / helpers: they launch what the user opted into, and a quit does not leave an orphan updating itself unless that is the documented helper.
- `NSWorkspace` launch or activate callbacks: errors surface; success is not assumed.

Do not install a real login item on this machine as a test unless the user named that.

### Recipe: sleep/wake or display unplug (when relevant)

- **Prerequisites:** a local debug build you are allowed to run, or a static trace if you cannot run UI.
- **Input:** sleep/wake or detach the screen the window is on (or read the observers and state updates if you cannot).
- **Expected fail:** window off-screen with no recovery, duplicate timers, or a status item that never returns.
- **Expected pass:** the window or extra is recoverable; work is not doubled.
- **Artifact:** notes in `lifecycle.md` or `evidence.md`.
- **ROI / stop:** apps that store windows or run extras. Skip a CLI-only helper.
