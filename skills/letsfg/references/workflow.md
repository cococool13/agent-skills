## Complete Workflow

### Flight Booking — PFS (2 API calls, free)

```
1. POST /api/search                    → Search flights (FREE), returns search_id
2. POST /api/agent-book                → Book directly — no unlock step, no LetsFG fee
```

### Flight Booking — Developer API (5 API calls)

```
1. POST /api/v1/agents/register        → Get API key (once)
2. POST /api/v1/agents/setup-payment   → Attach payment card (once)
3. POST /api/v1/flights/search         → Search flights (FREE)
4. POST /api/v1/bookings/unlock        → Unlock offer (legacy, Developer API only) → returns booking_url
5. POST /api/v1/bookings/book          → Book flight (ticket price charged via Stripe)
```

### Hotel Booking (Developer API key required — the PFS Bearer token does not work here)

```
1. POST /api/v1/agents/setup-payment       → Card on file (required for SEARCH too)
2. POST /api/v1/hotels/destinations        → Place name → city_id
3. POST /api/v1/hotels/search              → Bookable rates (free, card still required)
4. POST /api/v1/hotels/book                → Returns booking_job_id — NOT a booking
5. GET  /api/v1/hotels/booking/{job_id}    → Poll ~20s until succeeded/failed
                                             → confirmation + pay_link + balance_due_by
6. POST /api/v1/hotels/cancel              → Optional; free until balance_due_by
```

5% is charged to the card at step 4 as a non-refundable reservation fee; the balance is paid
directly to the supplier through `pay_link` by `balance_due_by`, which is the supplier's own
auto-cancellation date. Never repeat step 4 for the same rate — that books the room twice.
