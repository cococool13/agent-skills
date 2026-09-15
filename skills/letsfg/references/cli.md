## CLI Usage

```bash
pip install letsfg

letsfg auth   # zero-amount card setup, nothing charged — 90-day Bearer token

# Search flights — prints search_id, needed for book
letsfg search LHR JFK 2026-04-15
letsfg search LON BCN 2026-04-01 --return 2026-04-08 --cabin C --sort price
letsfg search GDN BER 2026-05-10 --adults 2 --children 1

# Resolve locations
letsfg locations "New York"

# Book — free, ticket price only, no LetsFG fee, no unlock step
letsfg book off_xxx --search-id srch_xxx \
  --passenger '{"given_name":"John","family_name":"Doe","born_on":"1990-01-15","gender":"m"}' \
  --email john.doe@example.com

# Machine-readable output
letsfg search GDN BER 2026-03-03 --json
```

Developer API instead? `letsfg register` + `letsfg setup-payment` once, then
`letsfg search ... --api-key letsfg_...`, `letsfg unlock off_xxx --api-key letsfg_...`,
`letsfg book off_xxx --api-key letsfg_... --passenger '{"id":"pas_0",...}' --email ...`.
