# Ego browser on Cohen’s Mac

`~/.agents/skills/ego-browser` and `~/.local/bin/ego-browser` are app-owned
links that Ego Lite moves on every update. Do not edit the app bundle, replace
the CLI, copy its skill, or set a legacy workspace override.

## Which browser

| Client | Default web QA | Cohen’s logged-in Chrome |
| --- | --- | --- |
| Claude desktop (Code tab) | built-in browser pane | Claude in Chrome |
| Claude CLI | `ego-browser` | Claude in Chrome (`claude --chrome`) |
| Codex | `ego-browser` | Codex Chrome extension |
| Cursor | `ego-browser` | none; use the Ego Lite profile |
| Grok | `ego-browser` | none; use the Ego Lite profile |

Ego Lite holds its own logged-in profile, so it also covers sign-in tasks in
any client. If the chosen browser is not connected, report it, skip browser QA,
and finish the rest.

## Fast path

1. Run `ego-browser skill > "$TMPDIR/ego-guide.md"` once per session and read
   that file. It is the version-matched API guide (about 550 lines) and ends
   with `[ego-browser:skill] end of guide`. Re-read the file, not the command.
2. Call the CLI by the bare name `ego-browser`. It is on PATH, and the
   sandbox exclusions (Claude `excludedCommands`, Codex
   `~/.codex/rules/default.rules`) match that name. If ego lite is not
   running, start it first so the helpers do not run the stack and heap
   profilers:

   ```bash
   bash /Users/cococool/.agents/skill-overlays/ego-browser/scripts/start-performance.sh
   ```

   That script does nothing when ego is already running. Do not quit ego to
   apply it. Ego needs macOS window services that the agent sandbox blocks:
   "Failed to start ego lite" from a sandboxed call means rerun with full
   access, not that Ego is broken.
   Claude desktop Code-tab sessions ignore `excludedCommands` (checked
   2026-10-20), so there run `ego-browser nodejs` with the sandbox disabled
   on the first call. `ego-browser skill` works inside the sandbox.
3. One script per round. Batch the actions, wait for the expected state, and
   print one snapshot last.

```bash
ego-browser nodejs <<'JS'
const task = await taskSpace("short task name");
const page = task.page("p1");
await page.goto("https://example.com", { timeout: 10000 });
console.log({ spaceId: task.spaceId });
console.log(await page.snapshot());
JS
```

Keep the printed space ID and resume with `taskSpace(id)` and the same page
label. Use exactly one space per goal. Never open a new space to recover.

## Screenshots and viewport checks

`await page.screenshot({ path: "/absolute/path/shot.png" })` returns a file
path; inspect it with the client’s image tool. Use snapshots for targeting,
screenshots for visual QA, not both by default.

For responsive QA, use `page.cdp("Emulation.setDeviceMetricsOverride",
{ width, height: 800, deviceScaleFactor: 1, mobile: false })` at 380, 768 and
1280, then `Emulation.clearDeviceMetricsOverride`. If `page.info()` reports
zero size, the window may be minimized: get it with
`task.cdp("Browser.getWindowForTarget", { targetId: page.targetId })` and
restore it with `Browser.setWindowBounds` `{ windowState: "normal" }`.
Raw CDP invalidates refs; take a fresh snapshot afterwards.

Do not restart Ego, close user tabs, clear a profile, or change cookies as
routine recovery. A screenshot timeout is a failed check; report it.

## Health check

```bash
bash /Users/cococool/.agents/skill-overlays/ego-browser/scripts/health-check.sh
```

Uses a local fixture, verifies DOM interaction, viewport and a real PNG, and
finishes its own space in about 2 seconds (25-second limit). Run it only to
diagnose a failure, never before every action.

## Finish and handoff

Call `await task.finish({ keep: [] })` once after success. Use
`task.handOff()` when Cohen must act, and wait. Do not claim a user-owned
space without his authorization. Check state before retrying an external write.

Runtime signatures come from `ego-browser skill`, not this guide.
