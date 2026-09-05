---
name: rtk
description: "Use when the user asks about RTK, its token-savings reports, or large command output needs compact handling."

---

# RTK — Rust Token Killer

Token-optimized CLI proxy (60–90% savings on noisy dev commands). Installed via Homebrew.

Cursor has no RTK PreToolUse hook. Prefix high-output commands with `rtk`:

```bash
rtk git log --oneline | head -50
rtk npm test
```

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
