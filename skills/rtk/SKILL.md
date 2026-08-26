---
name: rtk
description: "Use when the user asks about RTK, its token-savings reports, or large command output needs compact handling."

---

# RTK — Rust Token Killer

Token-optimized CLI proxy (60–90% savings on noisy dev commands). Installed via Homebrew.

## Hook status

**Claude Code (verified 2026-08-13):** `hooks/pre-bash.sh` is registered as
`PreToolUse`, and its last block delegates to `rtk hook claude` for a fixed
allowlist of read-only, high-output commands:

```
git status/log/diff/show/branch, ls, tree, rg, grep, wc,
du, df, find, ps, env, cat, head, tail
```

Those are compressed automatically — **do not prefix them by hand.** Anything
outside the allowlist runs unfiltered; prefix `rtk` yourself when you want
compression there:

```bash
rtk npm test
```

To widen coverage, edit the `case` list in `hooks/pre-bash.sh` and re-run the
hook battery. Do not run `rtk hook claude` to register a second hook — it would
double-filter.

**Cursor:** no RTK PreToolUse hook. Prefix high-output commands yourself:

```bash
rtk git log --oneline | head -50
rtk npm test
```

**Other runtimes:** prefix `rtk` yourself unless you have confirmed a hook is
wired. Do not assume `rtk hook Codex` is registered.

## Meta commands (always call rtk directly, never proxied)

```bash
rtk gain              # token savings analytics
rtk gain --history    # command usage history with savings
rtk discover          # analyze agent history for missed opportunities
rtk proxy <cmd>       # run a raw command without filtering (debugging)
```

## Verify the install

```bash
rtk --version   # expect: rtk 0.43.0 or newer
which rtk       # expect: /opt/homebrew/bin/rtk
```

**Name collision:** if `rtk gain` errors, you likely have reachingforthejack/rtk
(Rust Type Kit) shadowing it on PATH. Check `which -a rtk`.
