## Error Handling

| Exception | HTTP Code | When |
|-----------|-----------|------|
| `AuthenticationError` | 401 | Invalid or missing API key |
| `PaymentRequiredError` | 402 | No payment method (legacy flow) |
| `OfferExpiredError` | 410 | Offer no longer available |
| `LetsFGError` | 422 | Invalid request parameters |
| `LetsFGError` | 429 | Too many requests (retry with backoff) |
| `LetsFGError` | 502 | Upstream airline/hotel API error |

### Authentication Failure Recovery

```python
from letsfg import LetsFG
from letsfg.connectors.auth import BearerTokenError

try:
    bt = LetsFG()  # reads the Bearer token from `letsfg auth`
    flights = bt.search("LHR", "JFK", "2026-04-15")
except BearerTokenError:
    print("Token expired or missing — run `letsfg auth` again")
```

Developer API:

```python
from letsfg import LetsFG, AuthenticationError

try:
    bt = LetsFG(api_key="letsfg_...")
    flights = bt.search("LHR", "JFK", "2026-04-15")
except AuthenticationError:
    # API key invalid or expired — re-register
    creds = LetsFG.register("my-agent", "agent@example.com")
    bt = LetsFG(api_key=creds["api_key"])
    bt.setup_payment(token="tok_visa")  # re-attach payment on the new key
```

### Rate Limit and Timeout Handling

```python
import time
from letsfg import LetsFG, LetsFGError

def search_with_retry(bt, origin, dest, date, max_retries=3):
    for attempt in range(max_retries):
        try:
            return bt.search(origin, dest, date)
        except LetsFGError as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)  # exponential backoff
            elif "timeout" in str(e).lower() or "504" in str(e):
                time.sleep(1)
            else:
                raise
    raise LetsFGError("Max retries exceeded")
```
