# Apple, design, and performance

Open this module when the inventory includes an Apple client, or when design and interaction quality are in scope.

## Family Controls and Screen Time

Authorization, selection, and enforcement live in different frameworks (FamilyControls, Device Activity, Managed Settings). Request authorization before you present pickers or apply shields.

`FamilyActivitySelection` holds tokens for applications, categories, and web domains. Pass `applicationTokens` and `webDomainTokens` to `ManagedSettingsStore`. Do not try to recover bundle ids or display names from those tokens for your own logic. Apple presents the picker so the app does not learn which apps the person chose.

Apple's own `FamilyActivitySelection` page is client-rendered and often fetches as an empty shell. The same overview, mirrored at third-party Apple-doc sites and quoted in WWDC22 session 110336's surrounding docs, says the values are opaque and that if a user, parent, or guardian revokes authorization, tokens issued while the app was authorized are voided. Treat that as platform documentation corroborated by the mirror and secondary writeups, and re-check developer.apple.com when you have a rendered page. After a revoke, clear shields and stop acting as if the stored selection is still valid.

The system picker (`FamilyActivityPicker`) is not customizable. Missing the Family Controls entitlement often fails closed or silently. Individual authorization (a person managing their own Screen Time) and family authorization (a parent managing a child) are different request paths. Test both if the product claims both.

Expect the hosting app may be unable to shield itself. Background work that applies or lifts shields belongs in the documented extension points, not in a hope that the main app is running.

These behaviors need a real device or a provisioned development build. A host unit test cannot fully prove them. Write that gap down.

### Recipe: revoke voids enforcement

- **Prerequisites:** a provisioned development build if you can run one; otherwise a static trace and a listed real-device gap.
- **Input:** authorize, select apps, apply a shield, then revoke Screen Time / Family Controls access (or simulate the revoked authorization status if the test harness can).
- **Expected fail:** shields stay up, or the app still treats stored tokens as live bundle identities.
- **Expected pass:** tokens are not reversed into bundle ids anywhere; revoke clears enforcement; the UI asks the person to authorize and select again rather than silently reusing void tokens.
- **Artifact:** device notes or a static path through authorization-status handling. Host unit tests are marked insufficient.
- **ROI / stop:** mandatory if you use these APIs. There is no lighter substitute for the opacity and revoke rules. Stop short of claiming a simulator run proved shields.

## SwiftUI, lifecycle, and permissions

- Prefer structured work (`.task`, task groups) so disappearing views cancel in-flight loads.
- Model screen state as an enum (idle, loading, loaded, empty, failed) rather than several booleans. That enum is a low-rank machine: types and tests, not a formal spec.
- Handle `scenePhase` changes: what stops in the background, what must schedule a `BGTask`, what must not assume it will be called again soon.
- Permission prompts need a pre-prompt explanation, a path for "don't allow," and a path to Settings after a revoke. Do not ask for a permission you do not use.
- Privacy manifests (`PrivacyInfo.xcprivacy`) must list required-reason APIs the app or its SDKs use. App Review rejects missing entries.

## Accessibility and Dynamic Type

- Dynamic Type: text and tap targets must grow. Use the system text styles and `@ScaledMetric` for custom spacing that should scale. Check the largest accessibility sizes, not only the default.
- VoiceOver labels on icon-only controls. Don't rely on color alone.
- `Reduce Motion`: skip or shorten decorative animation when the user asked for less motion. Functional state changes should still be obvious without motion.
- These checks on a simulator's Accessibility Inspector are useful and still not a substitute for a VoiceOver pass on a device.

This matches common Apple HIG guidance. If you need the current wording, open the HIG pages for Dynamic Type and reduced motion rather than treating this file as a substitute.

## Empty, loading, and error

Every screen that loads data needs a loading presentation, an empty presentation with a next action, and an error presentation with a retry. Ask someone (or an agent) to break the screen: slow network, zero records, 401, 500, cancelled request. Snapshot those three states if you snapshot anything.

### Recipe: three states of a data screen

- **Prerequisites:** a way to stub the loader (zero rows, delay, 401/500).
- **Input:** open the screen in each stubbed condition.
- **Expected fail:** a blank screen, a spinner that never ends, or an error with no retry.
- **Expected pass:** named loading, empty-plus-next-action, and error-plus-retry presentations.
- **Artifact:** screenshots or snapshots in the run folder; optional snapshot tests in the repo.
- **ROI / stop:** worth it on user-facing data screens. Do not promote these three states into a TLA+ spec unless they interact with a high-rank machine.

## Performance, battery, memory, frames

- Measure with the same tools you will trust later (Instruments, `os_signpost`, metricKit hang rate, energy logs). Do not invent budgets.
- Main-thread work longer than a frame shows up as scroll hitches. Move decoding, JSON, and image work off the main thread.
- Avoid allocating in a hot per-frame or per-tick path. If the project has a naming or lint rule for hot files, keep it.
- Battery: wakeups, GPS, radios, and background modes cost more than CPU in a tight loop. Prove a change with before and after numbers from the same device.
- A benchmark that runs against a warm cache or a local mock is not a production number. Say what it measured.

## Stop

You can leave this module when each in-scope screen has loading/empty/error, permission revoke behavior is named, Family Controls tokens (if used) are treated as opaque, and any performance claim has a command and a number or is marked unmeasured.
