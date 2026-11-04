---
name: launch-qa-five-personas
description: "Use before any web launch, public deploy, or big landing-page change: five simulated first-time visitors test the real deployed or preview site in a real browser and return a ranked findings table with a pass/fail verdict."
argument-hint: "<live or preview URL> [success goal]"
---

# Launch QA: five first-time visitors

Source: https://x.com/RoundtableSpace/status/2111717667228770611 ("Act as my launch QA lead. Spin up 5 subagents, each a different first-time user … Merge everything into one list ranked by how many users hit it. Fix it all in one pass, then rerun the 5 users to prove it's fixed."). Adapted for Cohen: evidence required, blockers gate `/ship`, nothing real gets submitted.

## Inputs

- **URL:** the real deployed or preview URL (Cloudflare preview or production). Never a local mock, a static screenshot, or the source code alone.
- **First success:** the one thing a new visitor came to do (for example: find an offer and open its claim link, start checkout in test mode, sign up, download the app). Take it from the project's `AGENTS.md` / brief. If none is written, state your pick in one line.
- **Browser:** a real browser through Playwright, Chrome DevTools MCP, or the client's browser (routing in `~/.agents/AGENTS.md`). If no browser connects, stop and report "Launch QA did not run: no browser". Do not judge from code.

## Guardrails

- Never submit a real payment. Use Stripe test mode, a preview with test keys, or stop at the checkout page and confirm it loads with the right product and price.
- Never submit a form that emails a person, writes to a production list, or messages a sponsor or customer. Fill the form, check the validation, and stop before submit. Submit only on a preview with a test inbox, or when Cohen says so.
- No new accounts on third-party services. No real personal data. Use `test+qa@example.com`-style values.
- No invented results. Every finding has evidence. If a check could not run, mark it "not run" and give the reason.
- Read-only toward production data. Do not fix code during the run. Fixes come after the report.

## The five visitors

Run each visitor in a fresh browser context (no cookies, no cache). Use subagents if the client has them, else run them one after the other. Each starts at the landing page and goes for the first success.

| # | Visitor | Mission | What they try | Fail when |
|---|---------|---------|---------------|-----------|
| 1 | **Impatient** | Reach the first success as fast as possible. | Skims. Clicks the first button they see. Does not read body copy. Quits at the first error or dead end. | The main action is not obvious within 5 s. First success needs more than 3 clicks or more than 60 s. Any error, spinner over 3 s, or dead link on the path. |
| 2 | **Skeptic** | Decide whether to trust the site before signing up or paying. | Reads pricing, terms, privacy, refund and renewal terms, About, contact. Checks that claims and numbers have a source. | Missing privacy policy or terms. Renewal terms not next to the subscribe button. A claim, metric, logo, or testimonial with no real source. Price differs between pages or from checkout. |
| 3 | **Mobile** | Do the whole flow on a phone. | 375 × 667 viewport, touch, throttled to Slow 3G (or the closest preset). | Horizontal scroll. Text under 14 px or cut off. Tap targets under 44 px or overlapping. Sticky bars covering the action. LCP over 4 s on Slow 3G. Any step that only works with a mouse. |
| 4 | **Non-native English speaker** | Finish the flow using only what the UI literally says. | Follows labels word by word. Does not guess at idioms, puns, or icon-only buttons. | A label that needs context to understand. An idiom or slang term on the path. An icon-only action with no accessible name. An error message that does not say what to do next. Copy that breaks ASD-STE100 on the path. |
| 5 | **Breaker** | Make the site fail. | Pastes junk (emoji, 5,000 characters, `<script>`, SQL quotes, spaces only) into every field. Leaves required fields empty. Double-clicks every submit. Hits Back and Refresh mid-flow. Opens the flow in two tabs. Disables JavaScript once. | A 500 or blank page. Junk accepted without a clear error. Bad input does not return a 4xx on API routes. A double-click creates two records or two charges. Back or Refresh loses state with no warning. Unescaped input rendered on the page. Content invisible with JavaScript off. |

All five also record: console errors and warnings, failed network requests (4xx/5xx), and page timings (time to first meaningful paint or LCP, and time to first success).

## Evidence per finding

- Screenshot at the moment of confusion or failure (path under `docs/qa/<YYYY-MM-DD>/<visitor>/`). Screenshot at `scale: 0.5` unless detail matters.
- URL, viewport, and the exact step.
- Console error text or the failed request (method, path, status).
- Timing in seconds when the finding is about speed.
- One line: what the visitor expected versus what happened.

## Output

Write `docs/qa/<YYYY-MM-DD>-launch-qa.md` in the project and give the path plus the verdict in the reply.

1. **Verdict:** `PASS` or `FAIL`, in the first line. FAIL when any blocker is open.
2. **Ranked findings table**, sorted by severity, then by how many visitors hit it:

| Rank | Severity | Finding | Visitors who hit it | Evidence | Suggested fix |
|------|----------|---------|---------------------|----------|---------------|

3. **Severity:**
   - **Blocker:** a visitor cannot reach the first success; payment, signup, or a legal page is broken or missing; data loss, double charge, security issue, 500, or a console error on the path; mobile layout broken on the path.
   - **Major:** first success is reached but with real friction (confusing label, slow step, missing error message).
   - **Nit:** polish, copy, spacing, or an off-path issue.
4. **Not run:** each check that could not run, and why.

## After the report

When Cohen or the build prompt says to fix: fix every blocker and major in one pass, redeploy the preview, then rerun all five visitors on the new build. Ship only when the rerun verdict is PASS. Attach both reports.
