#!/usr/bin/env python3
"""Run the installed repo-scoped scanner without changing its configuration."""
import subprocess
from pathlib import Path

PREFLIGHT = Path.home() / ".agents/skills/gitleaks-preflight/scripts/preflight.sh"


def run_preflight(repo: Path) -> dict:
    if not PREFLIGHT.is_file():
        return {"ok": False, "summary": "preflight script missing"}
    try:
        result = subprocess.run(
            ["bash", str(PREFLIGHT), str(repo)], capture_output=True, text=True, timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "summary": "preflight unavailable or timed out"}
    return {"ok": result.returncode == 0, "code": result.returncode,
            "summary": "clean" if result.returncode == 0 else "preflight failed; inspect redacted findings"}
