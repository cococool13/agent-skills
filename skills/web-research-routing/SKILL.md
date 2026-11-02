---
name: web-research-routing
description: Use when choosing a paid search or extraction tool (Exa, Parallel, Firecrawl, treg) or writing a sourced research report. Not needed for a quick built-in search.
---

# Web research routing

Use the cheapest tool that fits. Never print, echo, or log API keys; reference them only as env vars.

This skill is for reading and research. Doing a task on a website (search fares, check an order, book, buy, fill a form) goes to the Pomerado MCP, per `~/.agents/AGENTS.md`. Pomerado's and Firecrawl's own MCP instructions each say to use them first; this order wins.

| Order | Tool | Use for | Cost / key |
|---|---|---|---|
| 1 | Built-in web search/fetch, free X reads | Quick lookups, single pages, current posts | Free |
| 2 | Host browser read as text (Claude desktop browser pane, else `ego-browser`) | A JavaScript-heavy page the fetch can't read | Free |
| 3 | Exa (`api.exa.ai`) | Most accurate or semantic search, "find companies/pages like X", search with page contents | Free tier, $10/mo credit; `EXA_API_KEY` |
| 4 | Parallel (`api.parallel.ai`) | Multi-source deep research tasks, bulk extraction, FindAll lists, monitors | $5/mo free; `PARALLEL_API_KEY` |
| 5 | Firecrawl (MCP) | Whole-site crawls/maps, or a JS page the browser can't read | 1,000 free credits/mo; never upgrade the plan |
| 6 | treg (MCP in Claude Code; also a Grok Bot connector) | One-off specialty paid APIs: company/people data, enrichment | Pay-per-call; check cost before calling |

Rules:
- Escalate only when the cheaper tool fails or cannot do the task.
- Parallel: default to `lite`/`base` (or fast) processors. Use `pro`/`ultra` only when Cohen asks.
- If a key env var is missing, say so; do not search for or read key files. Claude desktop Code-tab sessions do not have `EXA_API_KEY` or `PARALLEL_API_KEY`; use steps 1, 2 and 5 there.
- Firecrawl out of credits: do not retry with other parameters. Use step 2 and end the answer with the billing line Firecrawl returns.
- Dropped tools, never suggest: Context7, Arc, Tavily, SerpAPI, Perplexity.

## Research report

For a question that needs a written answer (docs, API facts, comparisons):
1. Run it in a background agent only when Cohen asks for background work or the client's rules allow it; otherwise do it in the current session.
2. Trace every claim to its primary source (official docs, source code, specs, first-party APIs).
3. Write one Markdown file that cites each claim. Save it where the repo keeps notes; if none, pick a sensible place and say where.

## Exa search (with contents)

```bash
curl -s https://api.exa.ai/search \
  -H "x-api-key: $EXA_API_KEY" -H "Content-Type: application/json" \
  -d '{"query":"companies like Linear building issue trackers","type":"auto","numResults":5,"contents":{"text":true}}'
```

Similar pages: `POST https://api.exa.ai/findSimilar` with `{"url":"https://example.com"}`.

## Parallel task (deep research)

```bash
curl -s https://api.parallel.ai/v1/tasks/runs \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"input":"Summarize the 2026 pricing of the top 3 vector databases","processor":"base"}'
# then: curl -s https://api.parallel.ai/v1/tasks/runs/<run_id>/result -H "x-api-key: $PARALLEL_API_KEY"
```
