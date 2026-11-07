# Network, Keychain, privacy, and IPC

## Network and auth

- Transport is HTTPS (ATS). Exceptions in `NSAppTransportSecurity` are named and justified.
- Tokens live in Keychain (or an equivalent protected store), not in UserDefaults or log lines. Read Keychain usage in code; do not dump items.
- Logout and uninstall stories: tokens can be discarded.

## Logs and privacy

Redact tokens, emails, file contents, and document titles if those are sensitive in this product. A debug log that prints a URL including a token is a finding; do not copy the secret into the report.

## URL schemes and files

- Custom URL schemes and universal links parse defensively: unexpected hosts, extra path segments, and `..` do not open arbitrary files or run unexpected actions.
- Any path built from user input, documents, or IPC is resolved and checked against an allowed root. Follow symlinks carefully so a link cannot escape the container or the user-chosen folder.
- Temporary files go in a directory you control, not a shared world-writable location with a guessable name.

## XPC and helpers

If XPC services or privileged helpers exist: authenticate the peer (code signing requirement), validate messages, and do not expose a "run this argument" interface. Helpers should not widen TCC or file access beyond their job.

### Recipe: hostile URL scheme (fixture)

- **Prerequisites:** the parser under test, no live system handler registration required.
- **Input:** a fixture URL with `../`, an unexpected host, or extra actions.
- **Expected fail:** the parser opens a path outside the intended root or triggers an unintended action.
- **Expected pass:** rejection or a safe no-op.
- **Artifact:** a unit test.
- **ROI / stop:** each declared scheme and document type.
