## Present Findings

Do not dump every result. Give the user a short research summary before designing when
the task is non-trivial.

Suggested format:

```text
Research summary:
- Styles reviewed: [count] across [directions]
- Screens reviewed: [count], if used
- Flows reviewed: [count], if used

Visual direction:
- [primary style foundation]
- [reference lock / signature traits to preserve]
- [borrowed detail 1]
- [borrowed detail 2]

Product patterns:
- [concrete UI decisions from screens]

Journey logic:
- [flow decisions, if applicable]

Recommendation:
- [what to design and why]
```

Before implementation, convert research into a short decision ledger:

| Decision | Source | Source rule / role | Why |
|----------|--------|--------------------|-----|
| [palette/type/layout/media/content choice] | [style/screen/flow/user constraint/craft rule] | [token/component/media role to preserve] | [specific rationale] |

If a major choice has no source, do not ship it as a design decision. Either research
more, tie it to the user's constraints, or remove it.
