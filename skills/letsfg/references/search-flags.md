## Search Flags Reference

| Flag | API Field | Values | Default |
|------|-----------|--------|---------|
| `--adults` | `adults` | 1–9 | 1 |
| `--children` | `children` | 0–9 | 0 |
| `--infants` | `infants` | 0–9 | 0 |
| `--cabin` | `cabin_class` | M (economy), W (premium), C (business), F (first) | _(any)_ |
| `--return` | `return_from` | YYYY-MM-DD | — |
| `--max-stops` | `max_stopovers` | 0–4 | 2 |
| `--sort` | `sort` | price, duration | price |
| `--limit` | `limit` | 1–100 | 20 |
| `--currency` | `currency` | EUR, USD, GBP, etc. | EUR |

### Cabin Class Codes Explained

| Code | Class | Description | Typical Use Case |
|------|-------|-------------|------------------|
| `M` | Economy | Standard seating | Budget travel, most bookings |
| `W` | Premium Economy | Extra legroom, priority boarding | Long-haul comfort without business price |
| `C` | Business | Lie-flat on long-haul, lounge access | Corporate travel, 6+ hour flights |
| `F` | First | Private suites, premium dining | Ultra-premium routes (limited airlines) |
| `--json` | — | Output as JSON | — |
