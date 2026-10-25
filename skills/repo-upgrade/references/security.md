# Security

## Primary: Cloudflare `security-audit` (full audit mode)

Read its `SKILL.md` from the path in `facts.md`, then run it as written. Settings:

| Setting | Value |
| --- | --- |
| Mode | full audit (this request is an explicit codebase audit) |
| Output dir | `<run>/security/` (outside the target; never inside it) |
| Profile | `standard`; `--quick` -> `quick`; `--deep` -> `deep` |
| Scope | this run's scope; anything else `out_of_scope`, never `covered` |
| Prior runs | earlier `~/.repo-upgrade/<repo>/run-*/security/` folders |
| Budget | none unless the user set one; for a large repo propose one first |

It does not modify source and must end in one of its two terminal states:
all artifacts written and both validators passing, or `run_status: incomplete`
with a reason. Requirements: parallel sub-agents and Node (for
`validate-findings.cjs` and `validate-coverage-ledger.cjs`). Without an
OS-enforced sandbox it does not execute target code; leads stay
`needs_validation`. That is correct, not a failure.

Feed back into repo-upgrade:
- `confirmed` records -> `findings.md` with their severity and smallest fix.
- `needs_validation` -> owner report, with the exact missing fact and safe check.
- `rejected` -> never re-raised by the quality lanes.
- Its `coverage-ledger.json` gaps -> "Not checked".

## Fallback lane (no sub-agents, no Node, or `--no-security`)

One read-only agent, trust-boundary method. A finding must name all six:
lower-trust actor, input or action they control, the control that should
stop them, the boundary crossed, the affected principal or resource, the
concrete result. Missing one = hardening note, not a finding.

Hunt by boundary:
- Injection: untrusted input to SQL, shell, HTML, templates, paths,
  redirects, deserializers, logs, secondary stores; also via keys, headers,
  field names, stored-then-reused data.
- Access control: right check, right resource, right mechanism, on every
  route and object ID (IDOR, tenant crossing, role confusion).
- Auth and sessions: token entropy and storage, comparison, expiry,
  recovery, deep links and invite codes as bearer secrets.
- Data exposure: secrets, codes or PII in URLs, logs, analytics, referrers,
  crash reports, third-party SDKs.
- Secrets hygiene: committed credentials, scanner allowlists that exempt the
  files a forced add would leak.
- Supply chain and CI: unpinned actions, write tokens, `pull_request_target`
  with checkout of PR code, scripts fetched at build time, ungated releases.
- Availability: unbounded bodies, loops, fan-out, work inside a lock; spend
  an attacker can trigger.
- AI surfaces: prompt or tool injection, model-controlled actions, secrets in
  context, unbounded tool loops.
- Mobile/desktop: exported components, URL schemes, webview bridges, local IPC.

Verdicts: `confirmed` (source trace plus bounded local evidence) gets a
severity; `needs_validation` (decisive fact lives outside the repo) gets the
missing fact and a safe check, no severity. Severity anchors: critical =
unauthenticated code execution, full data access, or arbitrary account
takeover; high = an explicit control fully defeated with real consequences;
medium = real violation, narrow blast radius or rare preconditions; low =
non-secret disclosure or high effort for little. If you cannot state the
damage, it is lower than it feels. Every fallback finding goes to a fresh
refuter (`verify.md`).
