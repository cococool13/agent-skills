# Inventory, baseline, and kind routing

Walk the scoped tree once. Write `map.md` and `coverage.md`. Infer app kind and distribution from evidence in the repo — do not assume Mac App Store or App Sandbox.

## Detect kind

| Kind | Typical signals | Extra emphasis |
| --- | --- | --- |
| SwiftUI app | `WindowGroup`, `@main` `App`, `NavigationStack` | Scene phase, scene storage, document groups |
| AppKit app | `NSApplication`, nibs, `NSWindowController` | Window restoration, first responder, menu validation |
| Menu bar extra | `LSUIElement`, `NSStatusItem`, accessory `MenuBarExtra` | Activation policy, click vs menu, screen changes |
| Document app | `DocumentGroup`, `NSDocument`, UTTypes | File identity, versions, sandbox bookmarks |
| Media / utility | AVFoundation, capture, processing pipelines | Permissions that are actually used, energy, cancellation |

A target can match more than one row.

## Infer distribution

| Evidence | Inference |
| --- | --- |
| Sparkle (`SUFeedURL`, `SUPublicEDKey`, `SPUStandardUpdaterController`), `notarytool` scripts, Developer ID export, website DMG/ZIP docs | **Developer ID notarized download** (common default when these are present). Do not assume sandbox. |
| App Store provisioning, `com.apple.security.app-sandbox` required, StoreKit as the only updater, no Sparkle | **Mac App Store**. Sandbox is expected. |
| Mixed or missing signals | **Unknown.** Record what you saw. Check signing settings without filling gaps from habit. |

Both recipes are supported. Prefer the inferred path for which signing, sandbox, and update checks you run.

## Inventory

1. Read README, Xcode projects/packages, `Info.plist` / entitlements, updater config, installer notes.
2. List entry points: app launch, services, URL schemes, documents, status item, helpers (`SMAppService`, login items), XPC, notifications, intents.
3. Name actor, input, writes, outbound calls, and success for each.
4. List implicit state: window visibility, document dirty flags, sync, permissions, update checks.
5. Write `coverage.md` with inspected paths and gaps. Do not claim every file was reviewed.

Do not open secret files or Keychain items. Record that a secret-looking path exists.

Supported macOS versions and architectures come from deployment target, `Info.plist`, package dest, and any Sparkle `minimumSystemVersion` / `hardwareRequirements`. Compare those declarations to shipped binaries only if artifacts are already in tree.

## Baseline

Run documented `xcodebuild` or SwiftPM test/build commands if the toolchain is here. Resolve packages with the repo's own pins (`xcodebuild -resolvePackageDependencies` or `swift package resolve`); never update `Package.resolved` or install global tools to make a gate run. If the repo configures `swiftlint` or `periphery`, run them and treat hits as leads, not findings. If Xcode is missing, write `needs Xcode` and continue with static reading. Do not invent a second suite. Do not run against the user's installed copy of the app in `/Applications`.

## Stop

`map.md` names kind(s), inferred distribution, modules loaded, and modules not loaded. `coverage.md` lists gaps.
