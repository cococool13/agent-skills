## MCP Server Setup

**Remote (Streamable HTTP) — Developer API only:**

```json
{
  "mcpServers": {
    "letsfg": {
      "url": "https://letsfg.co/developers/api/mcp",
      "headers": {
        "X-API-Key": "letsfg_..."
      }
    }
  }
}
```

**Local (stdio) — free PFS path:**

```bash
npm install -g letsfg-mcp
LETSFG_BEARER_TOKEN=eyJ...  letsfg-mcp   # token from `letsfg auth`
```

The local server also accepts `LETSFG_API_KEY` instead, for the Developer API.
`book_flight` dispatches automatically based on which one is set.

## MCP Tools

| Tool | Description | Cost |
|------|-------------|------|
| `search_flights` | Search hundreds of airlines via server-side engine | FREE |
| `resolve_location` | City name → IATA code | FREE |
| `book_flight` | Book an offer. PFS: direct, no unlock step. Developer API: requires `unlock_flight_offer` first | Ticket price only, no LetsFG fee (PFS) |
| `unlock_flight_offer` | **[Developer API only]** Confirm price, reveal booking URL, reserve 30min. Legacy — not part of the agent flow | — |
| `setup_payment` | **[Developer API only]** Attach payment card | FREE |
| `get_agent_profile` | View usage stats | FREE |
