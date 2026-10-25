#!/usr/bin/python3
"""Create a ten-minute, one-command receipt after Cohen explicitly approves an action."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time


def issue(cwd: str, command: str) -> Path:
    if not os.path.isabs(cwd) or not command.strip():
        raise ValueError("cwd must be absolute and command must be non-empty")
    canonical = os.path.realpath(cwd)
    key = hashlib.sha256((canonical + "\0" + command).encode()).hexdigest()
    directory = Path.home() / ".agents" / "hooks" / "approvals"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    target = directory / f"{key}.json"
    temporary = directory / f".{key}.{os.getpid()}.tmp"
    data = json.dumps({"command_hash": key, "expires_at": time.time() + 600})
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(data)
    os.replace(temporary, target)
    os.chmod(target, 0o600)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    try:
        issue(args.cwd, args.command)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print("One-use approval recorded for this exact command and directory (10 minutes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
