## Ratings

The star rating shows in search results before anyone visits the page. A 4.5★ app converts 30–40% better than a 3.8★ app on the same keyword and creatives — below 4.0, better metadata cannot win the conversion battle. Fix the rating first, then aim for 4.5+.

- Trigger the native prompt (`SKStoreReviewController` / `RequestReviewAction`) only after a success moment: task completed, milestone hit. Never after a crash, never on first launch — the prompt captures the user's current emotional state, and Apple has been rejecting first-launch prompts since 2026.
- The system shows the prompt at most 3 times per 365 days per device — the API can be called anytime but the OS decides. Those 3 impressions are the entire budget; spend them only on high-emotion moments.
- Never gate features or content on leaving a rating (Guideline 3.2.2).
- Respond to negative reviews within 48 hours. Users can update their rating after seeing a response; a thoughtful reply flips 2-star reviews into 4-star ones.
- If 30+ reviews mention the same bug, fixing it is ASO work. Mention the fix in the update notes — reviewers notice.
- Asking for reviews in release notes is allowed and effective ("If you find X helpful, leaving a review really helps us out").

## Tags

Apple generates public-facing tags for every listing from metadata, AI analysis, and editorial curation. You cannot create tags — but you can manage them, and unmanaged tags misdescribe apps.

- Review generated tags in App Store Connect and deselect any that misrepresent the app — a wrong tag routes wrong-intent traffic that bounces, and human reviewers approve tags before they go live, so corrections stick.
- Tag changes need no new build.
- Attribution: installs from a searched tag count as Search traffic; installs from browsing tag results count as Browse — check both when measuring.
- Recheck tags quarterly and after every description or screenshot change, because those are the inputs Apple generates from.
