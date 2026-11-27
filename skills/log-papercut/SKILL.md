---
name: log-papercut
description: "Log a shipping, CI, hook, or tooling papercut to ~/Projects/_ops/reports/papercuts.jsonl so slow or broken steps get fixed at the source."
user-invocable: true
metadata:
  short-description: "Record CI/shipping friction at the source"
---

# Log Papercut

Use this habit whenever a check, hook, build, test, or deploy step wastes time, flakes, or fails for an infrastructure reason.

Run:

```bash
.ci/bin/log-papercut \
  --category <ci-slow|flake|hook|deploy|e2e|tooling> \
  --summary "<one-line description>" \
  --impact "<time lost or failure mode>" \
  --cause "<suspected root cause>" \
  --fix "<suggested source-level fix>"
```

(If the current repo has not yet synced `.ci/bin/log-papercut`, run `~/.agents/ci/bin/log-papercut`.)

Rules:
- Log once per distinct root cause; do not spam duplicate lines in a retry loop.
- Never include secrets, tokens, or private user data in any field.
- Fix small papercuts in the same PR when in scope; otherwise log and keep moving.
