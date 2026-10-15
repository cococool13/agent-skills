#!/usr/bin/env bash
# Current helper source is maintained in the Agent Skills checkout.
set -euo pipefail
exec python3 "${HOME}/Projects/Agent Skills/skills/maintain-skill-library/scripts/ego-health-check.py"
