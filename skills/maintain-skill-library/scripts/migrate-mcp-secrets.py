#!/usr/bin/env python3
"""One-time migration: move MCP bearer tokens from mcp.json to ~/.agents/mcp.env."""
from __future__ import annotations

import json
import re
from pathlib import Path

HOME = Path.home()
MCP = HOME / ".cursor/mcp.json"
ENV = HOME / ".agents/mcp.env"
EXAMPLE = HOME / ".agents/mcp.env.example"

BEARER = re.compile(r"^Bearer\s+(.+)$", re.I)


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip()
    return out


def write_env(path: Path, data: dict[str, str]) -> None:
    lines = [
        "# MCP tokens for ~/.cursor/mcp.json (${env:VAR} interpolation).",
        "# Restart Cursor after edits.",
    ]
    for key in sorted(data):
        if data[key]:
            lines.append(f"{key}={data[key]}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)


def main() -> int:
    if not MCP.is_file():
        print(f"missing {MCP}")
        return 1
    cfg = json.loads(MCP.read_text())
    servers = cfg.get("mcpServers", {})
    env = load_env(ENV)

    letsfg = servers.get("letsfg", {}).get("env", {})
    if token := letsfg.get("LETSFG_BEARER_TOKEN", ""):
        if not token.startswith("${env:"):
            env.setdefault("LETSFG_BEARER_TOKEN", token)
            letsfg["LETSFG_BEARER_TOKEN"] = "${env:LETSFG_BEARER_TOKEN}"

    refero = servers.get("Refero", {}).get("headers", {})
    auth = refero.get("Authorization", "")
    if auth and not auth.startswith("${env:"):
        m = BEARER.match(auth)
        if m:
            env.setdefault("REFERO_MCP_TOKEN", m.group(1))
            refero["Authorization"] = "Bearer ${env:REFERO_MCP_TOKEN}"

    posthog = servers.get("posthog", {}).get("headers", {})
    auth = posthog.get("Authorization", "")
    if auth and not auth.startswith("${env:"):
        m = BEARER.match(auth)
        if m:
            env.setdefault("POSTHOG_MCP_TOKEN", m.group(1))
            posthog["Authorization"] = "Bearer ${env:POSTHOG_MCP_TOKEN}"

    write_env(ENV, env)
    MCP.write_text(json.dumps(cfg, indent=2) + "\n")
    if not EXAMPLE.is_file():
        EXAMPLE.write_text(
            "# MCP tokens — copy to ~/.agents/mcp.env\n"
            "LETSFG_BEARER_TOKEN=\n"
            "REFERO_MCP_TOKEN=\n"
            "POSTHOG_MCP_TOKEN=\n"
        )
    print(f"updated {MCP.name} and {ENV.name} ({len(env)} vars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
