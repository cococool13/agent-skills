# Ego browser on Cohen’s Mac

Read the installed `~/.agents/skills/ego-browser/SKILL.md` first. It and
`~/.local/bin/ego-browser` are app-owned links. Do not edit the app bundle,
replace the CLI, copy its skill, or set a legacy workspace override.

Use the shell tool available in the active client. An app’s PATH can omit
`~/.local/bin`; use the absolute CLI path below. No Playwright or alternate
browser for web QA.

## Start, observe, and resume

```bash
"$HOME/.local/bin/ego-browser" nodejs <<'JS'
const task = await taskSpace("short task name");
const page = task.page("p1");
await page.goto("https://example.com", { timeout: 10000 });
console.log({ spaceId: task.spaceId, page: page.label });
console.log(await page.snapshot());
JS
```

Print and keep the numeric space ID. Later invocations use `taskSpace(id)`
and the same page label. Variables do not persist between shell invocations.
Use exactly one space for a goal. Reuse `p1` rather than making another tab.
The example URL demonstrates navigation; health checks use a local fixture.

Select actions from the observed snapshot. Batch independent actions, wait
for the expected state, and print the final snapshot. Use `page.fill`,
`page.click`, `page.waitForSelector`, `page.waitForURL`, or
`page.waitForFunction`; signatures are in the installed API reference.
Use `page.evaluate` for bounded in-page extraction. Do not guess Playwright
methods or legacy global helpers.

## Screenshots and viewport checks

`await page.screenshot({ path: "/absolute/path/shot.png" })` returns a file
path; inspect that file with the client’s image-viewing tool. It is not an
image buffer. Use screenshots for visual QA and snapshots for DOM targeting.

For responsive QA on an agent-owned page, use `page.cdp` with
`Emulation.setDeviceMetricsOverride` and `{ width, height: 800,
deviceScaleFactor: 1, mobile: false }` for widths 380, 768, and 1280. Inspect
`page.info()` and the resulting screenshots. Clear the override afterwards
with `Emulation.clearDeviceMetricsOverride`. Desktop resizing does not prove
real iPhone touch, Safari, Windows scaling, or high-contrast behavior.

If `page.info()` reports zero width/height, diagnose the window first:

```js
const win = await task.cdp("Browser.getWindowForTarget", {
  targetId: page.targetId,
}, { timeout: 5000 });
if (win.bounds?.windowState === "minimized") {
  await task.cdp("Browser.setWindowBounds", {
    windowId: win.windowId, bounds: { windowState: "normal" },
  }, { timeout: 5000 });
}
console.log(await page.info());
```

Use Browser commands through `task.cdp`, Page/Emulation commands through
`page.cdp`. Raw CDP invalidates refs; take a fresh snapshot before actions.
Do not persist target IDs or fabricate viewport metrics to hide a failure.
Do not restart Ego, close user tabs, clear a profile, or change cookies as
routine recovery. A screenshot timeout is a failed check; report it and
finish independent work instead of retrying forever.

## Health check

```bash
bash "$HOME/.agents/skill-overlays/ego-browser/scripts/health-check.sh"
```

The check uses a local data-page fixture, verifies DOM interaction, viewport
size and a real PNG, then finishes its own task space. It has a 25-second
process limit and never restarts the browser. It prints only fixture state.
Run it to diagnose connection/rendering problems, not before every action.
On failure, retain the printed space ID for diagnosis; never create a new
space to recover a stopped user task. Read the installed connection reference,
report the blocker, skip browser QA, and finish the rest of the work.

## Finish and handoff

Call `await task.finish({ keep: [] })` once after success. Retain result pages
only when needed by the user. Respect user control and browser-owned prompts;
use `task.handOff()` and wait for the user when required. Do not claim or take
over a user-owned space without authorization. Check state before retrying
any external write; a receipt alone does not prove the write succeeded.

Source: `~/Projects/Agent Skills/skills/maintain-skill-library/references/ego-browser.md`.
Runtime signatures always come from the installed Ego skill, not this guide.
