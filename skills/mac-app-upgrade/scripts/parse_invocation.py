#!/usr/bin/env python3
"""Parse invocation flags for portable upgrade skills.

Only an exact implement flag enables mutation from flags.
Misspelled or prefix-similar safety flags stay report-only.
This helper does not invent product commands and does not
look at a repository. Natural-language implement intent is
detected from non-flag words; an exact --implement is enough
on its own.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

IMPLEMENT_FLAGS = {"--implement", "--implement-locally"}
REPORT_FLAGS = {"--report-only"}
DEPTH_FLAGS = {"--quick": "quick", "--standard": "standard", "--deep": "deep"}
KNOWN = set(IMPLEMENT_FLAGS) | set(REPORT_FLAGS) | set(DEPTH_FLAGS)

IMPLEMENT_WORD = re.compile(
    r"\b(fix|fixes|fixed|apply|implement|implementation|patch|patches)\b",
    re.I,
)
# "upgrade" is the skill name and must not imply mutation.
# "Do not implement anything." is a report-only ask, so negated wording never counts.
NEGATED_IMPLEMENT = re.compile(
    r"\b(?:do\s+not|don['’]?t|never|no|without|not\s+to)\s+(?:\w+\s+){0,2}?(?:fix|fixes|fixed|apply|implement|implementation|patch|patches)\b",
    re.I,
)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            ins, delete, sub = curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)
            curr.append(min(ins, delete, sub))
        prev = curr
    return prev[-1]


def flag_body(flag: str) -> str:
    return flag.lstrip("-").lower().replace("_", "-")


def looks_like_implement_typo(flag: str) -> bool:
    body = flag_body(flag)
    if f"--{body}" in IMPLEMENT_FLAGS or flag in IMPLEMENT_FLAGS:
        return False
    compact = body.replace("-", "")
    if compact.startswith("impl") or "implement".startswith(body) or body.startswith("implement"):
        return len(body) >= 3
    return levenshtein(compact, "implement") <= 2 or levenshtein(compact, "implementlocally") <= 2


def looks_like_report_typo(flag: str) -> bool:
    body = flag_body(flag)
    if flag in REPORT_FLAGS:
        return False
    compact = body.replace("-", "")
    if compact.startswith("report") or "reportonly".startswith(compact):
        return True
    return levenshtein(compact, "reportonly") <= 2 or levenshtein(compact, "auditonally") <= 2


def classify(tokens: list[str]) -> dict:
    flags = [t for t in tokens if t.startswith("--")]
    positionals = [t for t in tokens if not t.startswith("--")]
    unknown = [f for f in flags if f not in KNOWN]
    suspicious = [f for f in unknown if looks_like_implement_typo(f) or looks_like_report_typo(f)]
    report_typos = [f for f in unknown if looks_like_report_typo(f)]
    implement_typos = [f for f in unknown if looks_like_implement_typo(f)]

    has_report = any(f in REPORT_FLAGS for f in flags)
    has_implement = any(f in IMPLEMENT_FLAGS for f in flags)
    nl_implement = any(IMPLEMENT_WORD.search(NEGATED_IMPLEMENT.sub(" ", p)) for p in positionals)

    notes: list[str] = []
    if has_report and has_implement:
        mode, reason = "report-only", "both --report-only and --implement present; report-only wins"
    elif report_typos:
        mode, reason = "report-only", "unknown flag looks like misspelled --report-only; failing safe"
        notes.append(f"suspicious report-only lookalikes: {', '.join(report_typos)}")
    elif implement_typos and not has_implement:
        mode, reason = "report-only", "unknown flag looks like misspelled --implement; not enabling mutation"
        notes.append(f"suspicious implement lookalikes: {', '.join(implement_typos)}")
        if nl_implement:
            notes.append("natural-language fix/apply words were ignored because a misspelled safety flag is present")
    elif has_implement:
        mode, reason = "implement-locally", "exact --implement (or --implement-locally); no extra fix wording required"
    elif nl_implement and not has_report:
        mode, reason = "implement-locally", "natural-language fix/apply/implement wording"
    else:
        mode, reason = "report-only", "default"

    depth = "standard"
    depths = [DEPTH_FLAGS[f] for f in flags if f in DEPTH_FLAGS]
    if len(depths) == 1:
        depth = depths[0]
    elif len(depths) > 1:
        depth = "standard"
        notes.append(f"multiple depth flags {depths}; using standard")

    def looks_like_path(item: str) -> bool:
        if item in {".", ".."} or "/" in item or item.startswith("~/"):
            return True
        return bool(re.search(r"\.[A-Za-z0-9]+$", item))

    non_intent = [item for item in positionals if not IMPLEMENT_WORD.fullmatch(item)]
    path_like = [item for item in non_intent if looks_like_path(item)]
    scoped = "."
    if path_like:
        scoped = path_like[0]
    elif len(non_intent) == 1:
        scoped = non_intent[0]
    extra_words = [item for item in positionals if item != scoped]

    return {
        "schemaVersion": 1,
        "mode": mode,
        "modeReason": reason,
        "depth": depth,
        "scopedPath": scoped,
        "extraWords": extra_words,
        "unknownFlags": unknown,
        "suspiciousSafetyFlags": suspicious,
        "implementFlagExact": has_implement,
        "reportOnlyFlagExact": has_report,
        "naturalLanguageImplement": bool(nl_implement),
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tokens", nargs="*", help="invocation tokens (usually $ARGUMENTS split)")
    parser.add_argument("--out", help="write JSON here; default stdout")
    args = parser.parse_args()
    result = classify(args.tokens)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path = __import__("pathlib").Path
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
