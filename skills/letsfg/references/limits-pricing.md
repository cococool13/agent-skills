## Rate Limits

| Endpoint | Rate Limit | Typical Latency |
|----------|-----------|------------------|
| Search flights | No hard limit (billing is the natural governor) | 2–5 s (discover) · 8–10 s to first results (full search) |
| Resolve location | 120 req/min | <1s |
| Unlock | 20 req/min | 2-5s |
| Book | 10 req/min | 3-10s |
| Search hotels | 30 req/min | 3-10s |
| Register | 5 req/min | <1s |

## Pricing Summary

| Action | Cost |
|--------|------|
| Search (flights, hotels, transfers, activities) | **Free** |
| Resolve locations | **Free** |
| Register agent | **Free** |
| Setup payment | **Free** |
| View profile | **Free** |
| Book flight (PFS, no unlock needed) | **The price shown on the offer** — no LetsFG fee |
| Unlock offer (Developer API only) | Legacy path, not part of the agent flow — use `book_flight` directly |
| Book flight (Developer API, after unlock) | **The price shown on the offer** |
| Hotel booking | Room price only |
| Hotel cancellation | Per cancellation policy |

## Key Facts

- Hundreds of airlines via server-side engine
- Hotels and activities via direct APIs
- Zero price bias — no demand inflation, no cookie tracking
- Typically cheaper than booking through a single OTA, because it compares airlines and the major booking sites in one pass
- Real airline PNR codes and hotel confirmations
- E-tickets sent directly to passenger email
- Search is always free and unlimited
- PFS (Bearer token): book directly, no unlock step, no LetsFG fee on booking
- Developer API: unlock reveals the direct booking URL, then book (legacy — the agent flow books directly)
- API designed for machines, not browsers
