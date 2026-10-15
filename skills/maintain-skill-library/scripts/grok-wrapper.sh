#!/bin/zsh
# Give Grok the existing MCP environment used by the other local clients.
set -euo pipefail
if [[ -f "$HOME/.agents/mcp.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$HOME/.agents/mcp.env"
  set +a
fi
exec "$HOME/.grok/bin/grok" "$@"
