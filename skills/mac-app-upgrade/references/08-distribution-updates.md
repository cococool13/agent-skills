# Distribution, signing, and updates

Infer Developer ID versus Mac App Store from `01`. This module is read-only on existing artifacts unless the user named a release action.

## Signing, hardened runtime, Gatekeeper

Apple's Gatekeeper guide (published 19 December 2024) says downloaded software should be from the App Store **or** signed by an identified developer **and notarized**, and that Gatekeeper asks before the first open. App Store apps are sandboxed; Developer ID downloads are not sandboxed unless their entitlements say so. Do not assume sandbox.

Read-only checks on artifacts already in the tree or a path the user named:

- `codesign --verify --deep --strict --verbose=2 <app>`
- `codesign -dv --entitlements :- <app>` (do not paste secret-bearing entitlements into chat if any appear)
- `spctl --assess --verbose --type execute <app>` (and `install` for packages) when present
- `stapler validate <app-or-dmg>` when a ticket may already be stapled

Look for hardened runtime (required for notarization), library validation vs Sparkle (Sparkle's own docs: hardened runtime / library validation can block locally signed debug loads; distribution uses Developer ID), leftover `get-task-allow` on a shipping build, and entitlements the app does not need.

Installer / DMG: clean layout (app plus an `/Applications` symlink is the usual Developer ID DMG advice from Sparkle), no extra executables the user did not expect, quarantine is Gatekeeper's job — do not instruct the user to strip quarantine (`xattr -d com.apple.quarantine`) as a support workaround.

## Notarization (read-only)

Validate existing notarization when an archive is present. Do **not** run `notarytool submit`, upload a bundle, or `stapler staple` as part of this skill unless the user explicitly named that release step. Apple developer notarization pages often render as empty shells here; rely on Gatekeeper's published description plus the project's own notarization scripts, and mark official HTML as thin if you cannot read it.

## Sparkle (only if an updater exists)

Sparkle's EdDSA (ed25519) signatures are **separate** from Apple code signing (Sparkle documentation, opened 2026-11-07):

- `generate_keys` stores the private key in the login Keychain and prints a public key for `SUPublicEDKey` in Info.plist. Do not export, print, or commit the private key. If you see a private key file in the repo, that is a must-fix; do not display its value.
- Updates (archives, deltas, packages) are signed with `sign_update` / `generate_appcast` (`sparkle:edSignature` plus length). Serve appcasts over HTTPS.
- Optional `SURequireSignedFeed` (Sparkle 2.9+) also signs the appcast and release notes. That signature is still EdDSA, not Apple's.
- Channels (`sparkle:channel`), `minimumSystemVersion`, `hardwareRequirements` (2.9+, e.g. `arm64`), major-upgrade `minimumAutoupdateVersion`, and recovery when an update cannot run (read-only volume, translocation) should match what you ship.
- Rotating keys: Sparkle allows rotating either the Developer ID certificate *or* the EdDSA key, not both at once, for regular app updates.
- Do not publish an appcast or upload a build from this skill without the user naming that action.

If there is no updater and the app is MAS-only, note that and skip Sparkle rows.

### Recipe: validate an existing archive (no submit)

- **Prerequisites:** a .app, .dmg, or .zip already on disk that the user pointed at, or a CI artifact in the repo.
- **Input:** the read-only `codesign` / `spctl` / `stapler validate` commands above.
- **Expected fail:** invalid signature, missing notarization ticket when the project claims it is notarized, or sandbox entitlements on a Developer ID app that does not intend to be sandboxed (or the reverse).
- **Expected pass:** signature, inferred distribution, and ticket status written down.
- **Artifact:** command transcripts in the run folder.
- **ROI / stop:** the current shipping artifact, not every old build.
