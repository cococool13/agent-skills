# Permissions and TCC

Open when `Info.plist` usage descriptions, entitlements, or code paths request privacy-protected resources. If the app never captures, never probes Accessibility, and never reads Files in a protected way, say so and keep this short.

## Least privilege

- Only request TCC permissions the app actually uses (Camera, Microphone, Accessibility, Screen Recording, Input Monitoring, Contacts, Calendars, Photos, Location, Reminders, Automation, Full Disk Access, and so on).
- Usage description strings exist and describe the real reason, in time — prompt at the moment of use, not at first launch "just in case."
- Denial and later revoke: the app still launches, explains what is unavailable, and offers a path to System Settings rather than crashing or looping the prompt.
- Never run `tccutil reset` (or any command that wipes privacy decisions) on the user's Mac. It is not a test strategy. Use a separate test account or mocked authorization APIs if the project has them.

Accessibility and Screen Recording are powerful. Check them only if the binary or source actually uses those APIs.

### Recipe: deny then use the feature

- **Prerequisites:** a way to run the feature without resetting TCC (mocked status, or instructions the user already approved for a throwaway VM — not this skill resetting the host).
- **Input:** the feature whose permission is denied.
- **Expected fail:** crash, tight prompt loop, or pretending the capture succeeded.
- **Expected pass:** a clear explanation and a non-destructive idle state.
- **Artifact:** notes or a unit test around the authorization wrapper.
- **ROI / stop:** each permission the app actually requests.
