# Journeys and conversion

Open when people use pages or forms. Skip for a JSON-only API with no UI, and say so in `map.md`.

Do not submit real production forms, subscribe real inboxes, fire live chat widgets into a shared queue, or complete paid checkout. Use fixtures, local previews, or static inspection of the form action and validation.

## Matrix

For each in-scope journey (landing → action, signup, pricing → checkout start, contact, search, account, documented secondary flows):

| Cell | What good looks like |
| --- | --- |
| Happy path | The primary action is obvious; success is confirmed in words and UI |
| Validation | Errors sit next to fields, survive refresh rules you document, and do not wipe the form blindly |
| Cancel / back | Back and escape return to a sensible place; unsaved work is not silently lost if the product promised persistence |
| Permission / auth | Signed-out and signed-in states; forbidden actions explain the next step |
| Empty / loading / error | Each has a designed state, not a blank box |
| Convert | The ask matches the page; no surprise legal or billing step after the click |
| Retry | Double-submit does not create two messages or two charges in the design |

Write cells or `N/A` with a reason. Unused or surprising paths are intentional (say why), dead, or a bug.

## Forms without sending them

Read action, method, hidden fields, client and server validation, and the success page or JSON contract. For file fields see `08-reliability-platform.md` if uploads exist. Prefer a local preview or documented test endpoint over any live URL.

If browser automation is needed, use a host-provided adapter only (see the entrypoint). Never drive a real "Send" against production.

### Recipe: inspect a form without submitting

- **Prerequisites:** the form markup or component, and any schema/action handler.
- **Input:** empty, invalid, too-long, and well-formed fixture values (not sent live).
- **Expected fail:** required fields accept empty values, errors vanish, or the handler has no server-side check.
- **Expected pass:** client and server reject bad input the same way; success copy matches the handler.
- **Artifact:** rows in `journeys.md` if you wrote that file.
- **ROI / stop:** every in-scope converting form. Stop when spam holes and validation gaps are named.
