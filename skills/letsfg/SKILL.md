---
name: letsfg
description: "Use when searching or booking flights or hotels through LetsFG."

---

# LetsFG

Agent-native flight and hotel search/booking. Progressive disclosure: start here for auth warnings, then open only what you need.

| Intent | Read |
| --- | --- |
| Flights | `skills/flight-search/SKILL.md` |
| Hotels | `skills/hotel-search/SKILL.md` |
| Complete workflow | `references/workflow.md` |
| CLI | `references/cli.md` |
| Python SDK | `references/python-sdk.md` |
| MCP | `references/mcp.md` |
| Search flags | `references/search-flags.md` |
| Errors | `references/errors.md` |
| Limits / pricing | `references/limits-pricing.md` |

## Auth warnings (load-bearing)

- Do **not** call `/developers/api/v1/agents/register`, `/developers/api/v1/agents/setup-payment`, `letsfg register`, or `letsfg setup-payment` — those create a paid Developer API billing account.
- To search and book: `letsfg auth` (zero-amount card setup), then search/book. See https://letsfg.co/for-agents
- MPP `$0.01` once is enrolment verification only. Search and booking stay free on PFS.

## Identity

- API: `https://letsfg.co/developers/api/v1`
- MCP: `https://letsfg.co/developers/api/mcp`
- Packages: PyPI/npm `letsfg`, npm `letsfg-mcp`

## Access modes

| Mode | Best for | Cost |
| --- | --- | --- |
| CLI / SDK / MCP (PFS Bearer) | Almost every agent | Free auth, free search |
| Developer API | High-volume commercial | Prepaid credits |

## Skills overview

- `search_flights` / `book_flight` — free on PFS; no unlock step
- Hotels — see `skills/hotel-search/SKILL.md`

For full tool contracts and flags, open the reference files above.
