#!/bin/zsh
# Give Grok only the two MCP tokens its config uses. Nothing else from
# ~/.agents/mcp.env enters the environment; values never reach argv or output.
set -euo pipefail
f="$HOME/.agents/mcp.env"
if [[ -r "$f" ]]; then
  while IFS= read -r l || [[ -n "$l" ]]; do
    l="${l#export }"
    case "${l%%=*}" in
      REFERO_MCP_TOKEN|POSTHOG_MCP_TOKEN)
        v="${l#*=}"; v="${v#[\"\']}"; v="${v%[\"\']}"
        export "${l%%=*}=$v"
        ;;
    esac
  done < "$f"
fi
unset f l v
exec "$HOME/.grok/bin/grok" "$@"
