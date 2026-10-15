#!/bin/zsh
# Use the shared environment loader for authenticated MCP connections.
set -euo pipefail
exec "$HOME/.claude/bin/with-mcp-env" "$HOME/.local/bin/cursor-agent-native" "$@"
