## Python SDK Usage

```python
from letsfg import LetsFG

bt = LetsFG()  # reads the Bearer token from `letsfg auth`

# Search
results = bt.search("LHR", "JFK", "2026-04-15")
for offer in results.offers:
    print(f"{offer.price} {offer.currency} — {', '.join(offer.airlines)}")

# Book — free, ticket price only, no LetsFG fee, no unlock step
result = bt.book(
    offer_id=results.offers[0].id,
    passengers=[{
        "given_name": "John",
        "family_name": "Doe",
        "born_on": "1990-01-15",
        "gender": "m",
        "phone_number": "+447123456789",
    }],
    contact_email="john@example.com",
    search_id=results.search_id,
)
if result["booked"]:
    print(f"Order: {result['order_id']}")
else:
    print(f"Booking link (nothing charged): {result['booking_url']}")
```

Developer API instead? `LetsFG(api_key="letsfg_...")`, then `bt.unlock(offer_id)`
before `bt.book(...)` — returns a `BookingResult` with `booking_reference` (PNR).
