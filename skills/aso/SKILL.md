---
name: aso
description: "Use when writing or auditing iOS App Store listing metadata, keywords, or creatives."

---

# App Store Optimization

Progressive disclosure: this root is the ranking model. Open references for field recipes and creatives.

| Topic | File |
| --- | --- |
| App Name / Subtitle / Keyword field | `references/metadata-fields.md` |
| Keyword research / intent clusters | `references/keywords.md` |
| Screenshots, icon, video, creatives | `references/creatives.md` |
| Ratings / tags | `references/conversion.md` |
| Localization / IAP / events | `references/localization-events.md` |
| Experiments / featuring / paid+organic | `references/experiments.md` |
| Iteration / metadata change mechanics | `references/iteration.md` |
| Audit checklist | `references/checklist.md` |

## Ranking model

Apple indexes ~160 characters of owned keyword surface across **App Name** (30), **Subtitle** (30), and **Keyword Field** (100). Description and promotional text are **not** indexed for App Store search (they affect conversion; description also feeds Apple tags + Google web indexing).

Also indexed: category, screenshot content (AI analysis), tags, in-app event names (reinforcement). Downloads and ratings matter for rank. ASO cannot fix a leaky product.

**Zero-overlap rule:** never repeat a word across name, subtitle, and keyword field.

## Ranking vs conversion

| Surface | Ranking | Conversion |
| --- | --- | --- |
| Keyword field | Yes | None |
| App name | Highest | Yes |
| Subtitle | Second | Yes |
| Screenshots | Yes (AI) | Primary |
| Icon / preview video | None | Yes |

Optimize ranking and conversion as separate jobs — do not pack keywords into screenshot captions.
