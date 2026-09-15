#!/usr/bin/env python3
"""Reapply approved local instructions; stop on upstream conflicts, never overwrite blindly."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def apply(root: Path, manifest: Path, check: bool = False) -> list[str]:
    data = json.loads(manifest.read_text())
    if data.get("version") != 1:
        raise ValueError("Unsupported instruction override version")
    pending = []
    for entry in data["edits"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid override path")
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Override leaves skill library: {relative}")
        text = path.read_text()
        updated = text
        for hunk in entry["hunks"]:
            before, after = hunk["before"], hunk["after"]
            if after and updated.count(after) == 1:
                continue
            if not before or updated.count(before) != 1:
                raise ValueError(f"Instruction override conflicts with upstream: {relative}")
            updated = updated.replace(before, after, 1)
        if updated != text:
            pending.append((path, updated))
    # Validate every file before writing any of them.
    if not check:
        for path, text in pending:
            path.write_text(text)
    return [str(path.relative_to(root)) for path, _ in pending]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / ".agents/skills")
    parser.add_argument("--manifest", type=Path, default=Path.home() / ".agents/skill-overlays/instruction-edits.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        paths = apply(args.root, args.manifest, args.check)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Instruction overrides need review: {exc}")
        return 1
    print(f"Instruction overrides valid; {len(paths)} file(s) {'would change' if args.check else 'changed'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
