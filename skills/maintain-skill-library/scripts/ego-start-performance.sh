#!/usr/bin/env bash
# Start ego lite with the sampling profilers off. No-op when it is already running.
# Do not quit a running instance. The app is signed with the kill flag, so these
# flags have to be passed at launch. The heap-profiler names match ego lite 0.6.0.16.
# A newer build keeps only --disable-stack-profiler, so a vendor feature list is not replaced.
set -euo pipefail

app="/Applications/ego lite.app"
if [[ ! -d "$app" ]]; then
  echo "ego lite is not installed" >&2
  exit 1
fi

if ps -axo comm= | grep -F -x -q "$app/Contents/MacOS/ego lite"; then
  exit 0
fi

ver="$(defaults read "$app/Contents/Info" CFBundleShortVersionString 2>/dev/null || true)"
args=(--startup-ego-browser-service --disable-stack-profiler)
if [[ "$ver" == "0.6.0.16" ]]; then
  args+=(--disable-features=AimEnabled,Glic,Journeys,OmniboxContextualSearchOnFocusSuggestions,OmniboxMiaZPS,OmniboxToolbelt,SessionRestoreInfobar,WebUIReloadButton,HeapProfilerReporting,HeapProfilerChurnReporting)
fi

open -a "$app" --args "${args[@]}"
