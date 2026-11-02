#!/bin/bash
# mac-dist.sh - read-only distribution checks for a Mac app.
# Usage: mac-dist.sh <file.dmg | file.zip | App.app | Name.xcarchive | https://url/to.dmg>
#        mac-dist.sh --selftest
# Never launches an app. A URL is downloaded to a mktemp dir that is deleted on exit.
# A DMG is mounted read-only/nobrowse and detached on exit. Output: key=value lines.
set -u
UA='cohen-ai-stack-audit/1.0 (+read-only)'

if [[ "${1:-}" == "--selftest" ]]; then
  rc=0
  for t in spctl stapler codesign hdiutil plutil curl ditto; do
    case $t in
      stapler) command -v xcrun >/dev/null && xcrun --find stapler >/dev/null 2>&1 && echo "ok stapler" || { echo "MISSING stapler"; rc=1; } ;;
      *) command -v $t >/dev/null && echo "ok $t" || { echo "MISSING $t"; rc=1; } ;;
    esac
  done
  # codesign on a system binary proves the parse path works without touching anything of the user's
  codesign -dv --verbose=2 /bin/ls 2>&1 | grep -q 'Identifier=' && echo "ok codesign-parse" || { echo "FAIL codesign-parse"; rc=1; }
  exit $rc
fi

IN="${1:?usage: mac-dist.sh <path|url>}"
TMP=$(mktemp -d)
MNT=""
cleanup() {
  [[ -n "$MNT" ]] && hdiutil detach "$MNT" -quiet >/dev/null 2>&1
  rm -rf "$TMP"
}
trap cleanup EXIT

SRC="$IN"
if [[ "$IN" =~ ^https:// ]]; then
  SRC="$TMP/dl/$(basename "${IN%%\?*}")"
  mkdir -p "$TMP/dl"
  code=$(curl -sSL -A "$UA" -m 300 -o "$SRC" -w '%{http_code} %{content_type} %{size_download}' "$IN")
  echo "download_http=$code"
fi
echo "input=$IN"
[[ -e "$SRC" ]] || { echo "missing_file=1"; exit 1; }
echo "size_bytes=$(stat -f %z "$SRC" 2>/dev/null)"

APP=""
case "$SRC" in
  *.dmg)
    echo "--- dmg"
    spctl -a -vvv -t install "$SRC" 2>&1 | sed 's/^/dmg_spctl: /'
    xcrun stapler validate "$SRC" 2>&1 | tail -1 | sed 's/^/dmg_stapler: /'
    codesign -dv --verbose=2 "$SRC" 2>&1 | grep -E 'Authority|TeamIdentifier|Timestamp|not signed' | sed 's/^/dmg_codesign: /'
    MNT="$TMP/mnt"; mkdir -p "$MNT"
    if ! echo Y | hdiutil attach "$SRC" -nobrowse -readonly -noautoopen -mountpoint "$MNT" -quiet >/dev/null 2>&1; then
      echo "mount_failed=1"; MNT=""; exit 0
    fi
    APP=$(find "$MNT" -maxdepth 2 -name '*.app' -print -quit)
    ;;
  *.zip)
    mkdir -p "$TMP/x"; ditto -x -k "$SRC" "$TMP/x" 2>/dev/null
    APP=$(find "$TMP/x" -maxdepth 2 -name '*.app' -print -quit)
    ;;
  *.xcarchive) APP=$(find "$SRC/Products" -maxdepth 3 -name '*.app' -print -quit) ;;
  *.app) APP="$SRC" ;;
esac
[[ -n "$APP" ]] || { echo "no_app_found=1"; exit 0; }
echo "--- app: $(basename "$APP")"
PL="$APP/Contents/Info.plist"
rd() { /usr/libexec/PlistBuddy -c "Print :$1" "$PL" 2>/dev/null; }
echo "bundle_id=$(rd CFBundleIdentifier)"
echo "short_version=$(rd CFBundleShortVersionString)"
echo "build_version=$(rd CFBundleVersion)"
echo "min_system=$(rd LSMinimumSystemVersion)"
echo "SUFeedURL=$(rd SUFeedURL)"
echo "SUPublicEDKey_present=$([[ -n "$(rd SUPublicEDKey)" ]] && echo yes || echo no)"
echo "ProductBuildVersion=$(rd ProductBuildVersion)"
echo "--- codesign"
codesign -dv --verbose=4 "$APP" 2>&1 | grep -E '^(Identifier|Format|TeamIdentifier|Timestamp|Authority|Signature|CodeDirectory)|flags=' | sed 's/^/codesign: /'
codesign --verify --deep --strict "$APP" 2>&1 | head -3 | sed 's/^/verify: /'; echo "verify_rc=${PIPESTATUS[0]}"
echo "entitlement_keys=$(codesign -d --entitlements :- "$APP" 2>/dev/null | grep -o '<key>[^<]*</key>' | sed -E 's/<\/?key>//g' | tr '\n' ' ')"
echo "provisioning_profile=$([[ -f "$APP/Contents/embedded.provisionprofile" ]] && echo yes || echo no)"
echo "--- gatekeeper"
spctl -a -vvv -t exec "$APP" 2>&1 | sed 's/^/app_spctl: /'
xcrun stapler validate "$APP" 2>&1 | tail -1 | sed 's/^/app_stapler: /'
