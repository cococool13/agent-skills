#!/usr/bin/env python3
"""Check Ego's current API on an isolated local fixture; never restart the browser."""
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main() -> int:
    cli = Path.home() / ".local/bin/ego-browser"
    if not cli.is_file() or not os.access(cli, os.X_OK):
        print("Ego CLI unavailable; read the installed connection reference.")
        return 1
    with tempfile.TemporaryDirectory(prefix="ego-health-") as temp:
        shot = Path(temp) / "fixture.png"
        script = r'''const task = await taskSpace("Ego local health check");
console.log(JSON.stringify({ spaceId: task.spaceId }));
const page = task.page("p1");
const html = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Ego health fixture</title><h1>Ego health fixture</h1><label for="message">Message</label><input id="message"><button id="apply">Apply</button><output id="result">Waiting</output><script>document.querySelector("#apply").onclick=()=>document.querySelector("#result").textContent=document.querySelector("#message").value;</script></html>';
await page.goto("data:text/html;charset=utf-8," + encodeURIComponent(html), { timeout: 8000 });
const snapshot = await page.snapshot();
if (!snapshot.includes("Ego health fixture") || !snapshot.includes("textbox")) throw new Error("Snapshot failed");
await page.fill("#message", "Ego passed");
await page.click("#apply", { label: "apply local health message" });
await page.waitForFunction(() => document.querySelector("#result").textContent === "Ego passed", undefined, { timeout: 5000 });
await page.cdp("Emulation.setDeviceMetricsOverride", { width: 380, height: 800, deviceScaleFactor: 1, mobile: false }, { timeout: 5000 });
const info = await page.info();
if (info.w !== 380 || info.h !== 800) throw new Error("Viewport failed");
await page.screenshot({ path: __SHOT__ });
await page.cdp("Emulation.clearDeviceMetricsOverride", {}, { timeout: 5000 });
const receipt = await task.finish({ keep: [] });
if (receipt.closedSpace !== true) throw new Error("Task cleanup failed");
console.log("Ego navigation, snapshot, interaction, viewport, screenshot and cleanup passed");
'''.replace("__SHOT__", json.dumps(str(shot)))
        try:
            result = subprocess.run([str(cli), "nodejs"], input=script, text=True, timeout=25)
        except subprocess.TimeoutExpired:
            print("Ego check timed out; inspect the printed space ID. No automatic retry or restart.")
            return 1
        if result.returncode:
            return result.returncode
        if not shot.is_file() or shot.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            print("Ego screenshot is not a PNG.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
