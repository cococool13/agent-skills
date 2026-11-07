# Public sources

Curated public references for the mac-app-upgrade skill. No private account data, bookmarks, or identity.

Retrieved 2026-11-07 (America/New_York) unless a publication date is listed. **Opened** means a primary page was read; **thin** means the official Apple HTML did not yield a usable body in this environment.

## Distribution and Gatekeeper

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [Gatekeeper and runtime protection](https://support.apple.com/guide/security/gatekeeper-and-runtime-protection-sec5599b66df/web) | Published 19 Dec 2024 | Downloaded software should be identified-developer signed and notarized (or from the App Store); first-open approval; App Store apps are sandboxed — Developer ID apps are not unless entitlements say so | opened |
| [Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) | current Apple doc | Official notarization overview | opened, body thin (JS-rendered) |
| [Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow) | current Apple doc | Official `notarytool` workflow | opened, body thin (JS-rendered) |

Read-only local checks (`codesign`, `spctl --assess`, `stapler validate`) are used instead of submitting builds. This skill does not run `notarytool submit` or staple a release unless the user names that action.

## Sparkle updates

| Source | Date | What we use it for | Status |
| --- | --- | --- | --- |
| [Sparkle documentation](https://sparkle-project.org/documentation/) | current (opened 2026-11-07) | EdDSA keys via `generate_keys` (private key in login Keychain, public `SUPublicEDKey`); EdDSA signatures are separate from Apple code signing; HTTPS appcasts; `generate_appcast`; optional `SURequireSignedFeed` (2.9+); Developer ID distribution notes; do not keep private keys on the update host | opened |
| [Publishing an update](https://sparkle-project.org/documentation/publishing/) | current (opened 2026-11-07) | `sign_update` / `sparkle:edSignature`; `minimumSystemVersion`; `hardwareRequirements` (`arm64`, 2.9+); channels; major upgrades | opened |

## Shared engineering

Object-level authorization, persist-before-ack webhooks (if a Mac app talks to such an API), risk-ranked formal methods, and evidence types follow the 2026-11-07 app-upgrade research. They apply only when those surfaces exist.

## Skill format

Public skill-format notes informed the entrypoint shape (progressive disclosure, trigger plus non-trigger, decision tables, fingerprint/resume). Those URL lists live in the sibling comparison packet if present.
