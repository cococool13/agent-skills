# Public sources

Curated public references behind the app-upgrade skill. No private account data, bookmarks, or identity.

Retrieved originally on 2026-11-07 (America/New_York). Spot-checked again on 2026-11-07 during quality review. Status: **opened** means a primary page was read this review; **located** means the URL exists but the body was thin, paywalled, or only partially used.

## Verification and formal methods

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [Hillel Wayne, Why Antithesis?](https://antithesis.com/blog/2026/hillel-joins-antithesis/) | Oct 30, 2026 | Verification tools are different tradeoffs, not a ladder. Model checking an atomic `if` hides the race that appears when the test and assignment are separate steps. DST controls nondeterminism in the real program. | opened |
| [Anthropic, formal verification](https://www.anthropic.com/research/formal-verification) | Oct 22, 2026 | "Formally verified" does not mean "bug-free." A proof is relative to the spec and the trusted machine model. Fuzz harnesses often already encode relations such as encode/decode. | opened |
| [Newcombe et al., How AWS uses formal methods](https://cacm.acm.org/research/how-amazon-web-services-uses-formal-methods/) | Apr 1, 2015 (CACM) | Industrial TLA+ on DynamoDB and other AWS systems found long design-level interleavings that reviews and tests missed. A checked model is not the executable code. | opened (full CACM page, this review) |
| [Lamport Amazon excerpt PDF](https://lamport.azurewebsites.net/tla/formal-methods-amazon.pdf) | companion to the CACM article | Same paper family. Not separately extracted this review. | located |

## Deterministic simulation

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [FoundationDB testing](https://apple.github.io/foundationdb/testing.html) | current FoundationDB 8.0 docs | Deterministic cluster simulation, fault injection, replay of a simulated run. | opened |
| [TigerBeetle VOPR](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/internals/vopr.md) ([raw](https://raw.githubusercontent.com/tigerbeetle/tigerbeetle/main/docs/internals/vopr.md)) | current main | Fake clock, network, and disk; seed plus commit replay; assertions and extra checkers. | opened (raw file) |
| [Protocol-aware DST](https://tigerbeetle.com/blog/2026-08-20-protocol-aware-dst/) | Aug 20, 2026 | Inside-out protocol checks versus black-box generative testing. Date confirmed. | opened |

## Idempotency, webhooks, payments

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [Brandur, idempotency keys](https://www.brandur.org/idempotency-keys) | Oct 27, 2017 | Recovery points, atomic phases, foreign mutations, per-user keys, lock, completer/reaper. Local ACID work can be one transaction; Stripe/email/queue calls cannot. | opened |
| [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests) | current docs | API v1: `Idempotency-Key` on POST, not useful on GET/DELETE; keys retained at least 24 hours; mismatched parameters error; UUID suggested; no personal identifiers as keys. API v2 differs (30-day window, POST and DELETE). | opened |
| [Stripe webhooks](https://docs.stripe.com/webhooks) / [signatures](https://docs.stripe.com/webhooks/signatures) | current docs | Verify over the raw body; HMAC; default 5-minute timestamp tolerance (0 disables it); new signature on each retry; no delivery-order guarantee; live retries up to three days; return 2xx before *complex* work and process asynchronously. Docs do **not** say to ACK before a durable write. This skill requires persist-or-enqueue, then 2xx, and 5xx if that write fails. | opened |

## Authorization and mobile security

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [OWASP API1:2023](https://raw.githubusercontent.com/OWASP/API-Security/master/editions/2023/en/0xa1-broken-object-level-authorization.md) | 2023 edition | Every endpoint that takes an object id must check the caller may perform that action on that object. UUID is not a substitute. Write tests; do not deploy changes that make them fail. | opened |
| [OWASP WSTG BOLA](https://wstg.owasp.org/latest/4-Web_Application_Security_Testing/12-API_Testing/02-API_Broken_Object_Level_Authorization/) | current WSTG | How to test object-level authorization. | located / snippet-confirmed |
| [IDOR cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html) | current | Related prevention notes. | located / snippet-confirmed |
| [OWASP MASVS](https://mas.owasp.org/MASVS/) | current | Mobile control groups: storage, crypto, auth, network, platform, code, resilience, privacy. Resilience is not mandatory for every consumer app. | opened |

## Apple platform

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [FamilyActivitySelection](https://developer.apple.com/documentation/familycontrols/familyactivityselection) | current | Official URL. Page body is client-rendered and fetched empty in this environment. | opened, body thin |
| [applicationTokens](https://developer.apple.com/documentation/familycontrols/familyactivityselection/applicationtokens) | current | Official token field docs; also thin in this environment. | located |
| [WWDC22 110336](https://developer.apple.com/videos/play/wwdc2022/110336/) | 2022 | Family Controls as a privacy-preserving gateway; opaque tokens that identify apps and websites; individual vs family authorization. | snippet opened |
| [Mirror overview](https://apple-docs.everest.mt/docs/familycontrols/familyactivityselection/) | unofficial mirror of Apple's overview | States that `FamilyActivitySelection` holds opaque values, and that if a user, parent, or guardian revokes authorization, tokens provided while the app was authorized are voided. Not apple.com. Use as corroboration until the official page renders. | opened |

## Practitioner essays on X (public posts)

These informed emphasis, not formal standards. Dates are the posts' own dates as recorded in the research window (2026-11-07). They were not independently re-fetched one-by-one in the quality-review pass.

- https://x.com/hillelogram/status/2115865880311767232 (2026-10-29)
- https://x.com/poteto/status/2111133080526495985 (2026-10-16) — mechanical checks before prose review
- https://x.com/poteto/status/2114626630429913383 (2026-10-26) — types, property tests, fuzzing, DST
- https://x.com/poteto/status/2115880102601101414 (2026-10-29) — implicit state machines / statechart
- https://x.com/poteto/status/2117043478140276847 (2026-11-01) — turn bugs into gates
- https://x.com/poteto/status/2117437607940681849 (2026-11-03) — spend review on runs
- https://x.com/zack_overflow/status/2117374627425231322 (2026-11-02) — deterministic simulation
- https://x.com/tianyin_xu/status/2113370522222510308 (2026-10-22) — TLA vs TLA+
- https://x.com/AntonMartyniuk/status/2112530008556159171 (2026-10-20) — webhook signatures
- https://x.com/copyconstruct/status/2118407331990147094 (2026-11-05) — SLOs and agent-written code
- https://x.com/emilkowalski/status/2115531147853607214 (2026-10-28) — break UI; success/error as machines
- https://x.com/jacobtechtavern/status/2110748485309854111 (2026-10-15) and https://x.com/mecid/status/2109595753685397681 (2026-10-12) — structured Swift concurrency / `.task`

## Honest gaps

- Kyle Kingsbury / `from:aphyr` originals were not present in the public search sample; Jepsen appears through other writers and through TigerBeetle's discussion of black-box generative testing.
- Metamorphic testing, virtual clocks, empty/loading/error as a triple, contract testing, and expand/contract migrations had weak X coverage. They are included as standard techniques with that caveat.
- Apple's official FamilyActivitySelection HTML is still JS-thin here; opacity and revoke-voids-tokens come from WWDC context plus the unofficial mirror.
- Stripe's own sample handlers often process the event and then return 200, which sits next to their "return 2xx before complex logic" advice. The skill follows the durable-inbox reading of that advice.


## Skill format (how this skill is written)

Public specifications and example skills that informed the 2026-11-07 agent-usability revision. They are not app-engineering citations. Retrieved 2026-11-07 (America/New_York).

| Source | What we used |
| --- | --- |
| [Agent Skills specification](https://agentskills.io/specification) | Frontmatter, progressive disclosure (metadata → SKILL.md → files on demand), optional `scripts/` / `references/` / `assets/` |
| [Anthropic skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | Third-person descriptions, degrees of freedom, ~500-line entrypoint, one-level-deep references |
| [Anthropic skill-creator](https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md) | Explain why, when-to-use in the description, iteration loop |
| [Anthropic document skill (`docx`)](https://raw.githubusercontent.com/anthropics/skills/main/skills/docx/SKILL.md) | Trigger plus do-not trigger text, decision table, verify-output helpers |
| [OpenAI / Codex skill-creator sample](https://raw.githubusercontent.com/openai/codex/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md) | Portable skill-creator shape |
| [OpenAI plugins: build skills](https://developers.openai.com/plugins/build/skills) | Host skill format notes |
| [ChatGPT: build skills](https://learn.chatgpt.com/docs/build-skills) | Description should/should-not trigger; front-load keywords |
| [obra/superpowers systematic-debugging](https://raw.githubusercontent.com/obra/superpowers/HEAD/skills/systematic-debugging/SKILL.md) | Sequential evidence-gathering before a fix |
| [obra/superpowers verification-before-completion](https://raw.githubusercontent.com/obra/superpowers/HEAD/skills/verification-before-completion/SKILL.md) | Fresh evidence before a claim |
| [caldoai untangle-codebase](https://raw.githubusercontent.com/caldoai/skills/main/skills/untangle-codebase/SKILL.md) | Decision log (not its "finish everything" loop) |
| [Vercel deploy-to-vercel](https://raw.githubusercontent.com/vercel-labs/agent-skills/main/skills/deploy-to-vercel/SKILL.md) | Cheap state checks and a decision tree (not its commit/push/deploy steps) |

House or identity-bearing skill URLs are intentionally omitted from this portable list.
