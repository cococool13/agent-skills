#!/usr/bin/python3
"""Stop hook: lint the files `git status --porcelain` lists in the cwd. Warn only.

Reuses the Biome/Ruff checks of ~/.claude/hooks/lint-on-edit.py, so edits made
through Bash (sed, heredocs, scripts) get the same check as Edit/Write.
Prints {"systemMessage": ...} when there are errors; always exits 0.
Usage: lint-dirty.py < hook-json  |  lint-dirty.py --selftest
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

LINTER = Path.home() / ".claude/hooks/lint-on-edit.py"
MAX_FILES, MAX_LINES = 40, 15


def checks():
    spec = importlib.util.spec_from_file_location("lint_on_edit", LINTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def dirty_files(cwd: Path):
    out = subprocess.run(["git", "status", "--porcelain", "-z", "--untracked-files=all"], cwd=cwd,
                         capture_output=True, text=True, timeout=10)
    if out.returncode:
        return []
    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True,
                               text=True, timeout=10).stdout.strip())
    files, entries = [], out.stdout.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        status, name = entry[:2], entry[3:]
        if status[0] in "RC":
            i += 1  # -z puts the old name next
        path = root / name
        if "D" not in status and path.is_file() and "node_modules" not in path.parts:
            files.append(path)
    return files[:MAX_FILES]


def lint(cwd: Path):
    mod = checks()
    errors = []
    for path in dirty_files(cwd):
        ext = path.suffix.lower()
        found = mod.biome(path) if ext in mod.BIOME_EXT else mod.ruff(path) if ext == ".py" else []
        errors += [f"{path.name}: {e}" if path.name not in e else e for e in found]
    return errors


def main():
    data = json.load(sys.stdin)
    if data.get("stop_hook_active"):
        return
    errors = lint(Path(str(data.get("cwd") or ".")))
    if errors:
        shown = errors[:MAX_LINES] + ([f"... {len(errors) - MAX_LINES} more"] if len(errors) > MAX_LINES else [])
        print(json.dumps({"systemMessage": "Lint errors in changed files:\n" + "\n".join(shown)}))


def selftest():
    import shutil
    import tempfile
    if not shutil.which("ruff"):
        print("lint-dirty selftest: skipped (no ruff)")
        return
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q", d], check=True)
        Path(d, "ruff.toml").write_text("")
        Path(d, "bad.py").write_text("import os\n")
        Path(d, "good.py").write_text("print(1)\n")
        errors = lint(Path(d))
        assert len(errors) == 1 and "bad.py" in errors[0] and "F401" in errors[0], errors
    print("lint-dirty selftest: ok")


if __name__ == "__main__":
    try:
        selftest() if "--selftest" in sys.argv else main()
    except AssertionError:
        raise
    except Exception:
        pass  # warn-only: never block a stop
