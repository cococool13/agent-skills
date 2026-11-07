# Persistence and file handling

Open when the app writes files, databases, or user defaults. Use a temporary directory as the fixture root. Do not read or write the user's real `~/Library/Application Support`, preferences, or caches for this app.

## Checks

- Writes that must not tear are atomic (write to a temp file, then replace). Crash mid-write leaves the previous good file or a recoverable journal.
- Security-scoped bookmarks for user-chosen files: start and stop accessing the resource; store bookmarks, not raw paths you cannot reopen after relaunch (especially outside a sandbox, and always inside one).
- Migrations have a version and a failure path. A failed migration does not delete user data to "start clean" unless the user confirmed that.
- File coordination / NSDocument autosave conflicts are handled; two windows do not clobber without notice.
- Symlinks and `..` components in any path the user or a document can influence are resolved safely (see `09-security-ipc.md`).
- Preferences: unexpected or missing keys do not crash launch.

### Recipe: crash during save (or simulate it)

- **Prerequisites:** a temp document and the save path in code.
- **Input:** interrupt after the temp write or inject a failure before replace (test double).
- **Expected fail:** the destination is zeroed or half-written with no backup.
- **Expected pass:** the previous file remains or the journal can restore it.
- **Artifact:** a unit test against a temp directory.
- **ROI / stop:** each durable store. Skip pure in-memory utilities.
