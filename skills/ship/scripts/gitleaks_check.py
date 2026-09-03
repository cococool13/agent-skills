#!/usr/bin/env python3
"""Run gitleaks preflight for the current repo."""

from __future__ import annotations

import subprocess
from pathlib import Path

PREFLIGHT = Path.home() / ".agents" / "skills" / "gitleaks-preflight" / "scripts" / "preflight.sh"
INIT = Path.home() / ".agents" / "skills" / "gitleaks-preflight" / "scripts" / "init-config.sh"


def ensure_config(repo: Path) -> bool:
    if (repo / ".gitleaks.toml").is_file():
        return True
    if not INIT.is_file():
        return False
    r = subprocess.run(["bash", str(INIT), str(repo)], capture_output=True, text=True)
    return r.returncode == 0 and (repo / ".gitleaks.toml").is_file()


def run_preflight(repo: Path) -> dict:
    if not PREFLIGHT.is_file():
        return {"ok": True, "skipped": "no preflight script"}
    ensure_config(repo)
    r = subprocess.run(["bash", str(PREFLIGHT), str(repo)], capture_output=True, text=True)
    tail = (r.stdout or r.stderr or "").strip().splitlines()
    summary = tail[-1] if tail else ("clean" if r.returncode == 0 else "failed")
    return {
        "ok": r.returncode == 0,
        "code": r.returncode,
        "summary": summary,
        "skipped": False,
    }
