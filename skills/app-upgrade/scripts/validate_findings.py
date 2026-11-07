#!/usr/bin/env python3
"""Check a run's findings.json against references/evidence.schema.json rules.

Stdlib only (no jsonschema dependency). Also enforces the contract rules the
schema cannot express: confirmed findings name a control and a resource,
confirmed-repro has a command, confirmed-static has a path, ids are unique.
Exit 0 = PASS, 1 = FAIL.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "references" / "evidence.schema.json"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_findings.py <run>/findings.json", file=sys.stderr)
        return 2
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    fdef = schema["$defs"]["finding"]
    props = fdef["properties"]
    try:
        doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL\n- cannot read: {exc}")
        return 1

    errors: list[str] = []
    if not isinstance(doc, dict):
        print("FAIL\n- top level must be an object")
        return 1
    extra = set(doc) - set(schema["properties"])
    if extra:
        errors.append(f"unknown top-level keys {sorted(extra)}")
    if doc.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    findings = doc.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be an array")
        findings = []

    seen: set[str] = set()
    for i, f in enumerate(findings):
        tag = f"findings[{i}]"
        if not isinstance(f, dict):
            errors.append(f"{tag} is not an object")
            continue
        tag = f"{tag} ({f.get('id', '?')})"
        for key in fdef["required"]:
            if key not in f:
                errors.append(f"{tag} missing {key}")
        for key in set(f) - set(props):
            errors.append(f"{tag} unknown key {key}")
        for key, spec in props.items():
            if key not in f:
                continue
            val = f[key]
            types = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
            ok = (val is None and "null" in types) or (isinstance(val, str) and "string" in types)
            if not ok:
                errors.append(f"{tag} {key} has wrong type")
            elif "enum" in spec and val not in spec["enum"]:
                errors.append(f"{tag} {key}={val!r} not in {spec['enum']}")
            elif spec.get("minLength") and isinstance(val, str) and len(val) < spec["minLength"]:
                errors.append(f"{tag} {key} is empty")
        fid = f.get("id")
        if fid in seen:
            errors.append(f"{tag} duplicate id")
        seen.add(fid)
        ev = f.get("evidenceType", "")
        if ev.startswith("confirmed-"):
            for key in ("control", "resource"):
                if not f.get(key):
                    errors.append(f"{tag} {ev} needs {key}")
        if ev == "confirmed-repro" and not f.get("command"):
            errors.append(f"{tag} confirmed-repro needs command")
        if ev == "confirmed-static" and not f.get("path"):
            errors.append(f"{tag} confirmed-static needs path (entry -> input -> check -> resource -> impact)")

    if errors:
        print("FAIL")
        for e in errors:
            print(f"- {e}")
        return 1
    print(f"PASS findings={len(findings)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
