#!/usr/bin/env bash
# cleanup-downloads.sh — idempotent weekly Downloads sorter for Cohen's Mac.
# Canonical taxonomy source. Safe to re-run. Never deletes; archives instead.
set -euo pipefail

DL="$HOME/Downloads"
TS="$(date +%Y-%m-%d)"
LOG="$DL/_archive/${TS}-cleanup-changelog.md"

mkdir -p "$DL"/{School/Spreadsheets,School/Code,School/Presentations} \
         "$DL"/{Career/PDFs,Career/Docs,Personal,Data} \
         "$DL"/{Media/Images,Media/Videos,Media/Installers,Media/Other} \
         "$DL"/{_inbox,_archive,_needs-review}

moved=0
log() { printf '%s\n' "$1" >> "$LOG"; }
log "# Downloads cleanup — $TS"; log ""

# move <src> <destdir>: collision-safe, idempotent
mv_safe() {
  local src="$1" dest="$2" base; base="$(basename "$src")"
  [ -e "$src" ] || return 0
  mkdir -p "$dest"
  if [ -e "$dest/$base" ]; then base="${base%.*}-$(date +%H%M%S).${base##*.}"; fi
  mv "$src" "$dest/$base" && { moved=$((moved+1)); log "- \`$1\` -> \`$dest/$base\`"; }
}

shopt -s nullglob
for f in "$DL"/*; do
  [ -f "$f" ] || continue
  name="$(basename "$f")"; ext="${name##*.}"; lc="$(echo "$ext" | tr 'A-Z' 'a-z')"
  case "$lc" in
    png|jpg|jpeg|gif|heic|webp)
      if [[ "$name" == Screenshot* || "$name" == SS\ * ]]; then
        clean="$(echo "$name" | tr -d '\342\200\257')"  # strip U+202F
        mv_safe "$f" "$HOME/Pictures/Screenshots"
      else mv_safe "$f" "$DL/Media/Images"; fi ;;
    mp4|mov|m4v|avi)      mv_safe "$f" "$DL/Media/Videos" ;;
    dmg|pkg)              mv_safe "$f" "$DL/Media/Installers" ;;
    zip|tar|gz|tgz|rar|7z) mv_safe "$f" "$DL/_archive" ;;
    csv|xlsx|xls)
      if echo "$name" | grep -qiE 'password|bitwarden|recovery|bank|statement'; then
        log "- ⚠️  CREDENTIAL/FINANCIAL: \`$name\` left in place — flag to user"
      else mv_safe "$f" "$DL/School/Spreadsheets"; fi ;;
    r|rmd|py|ipynb|js|ts) mv_safe "$f" "$DL/School/Code" ;;
    ppt|pptx|key)         mv_safe "$f" "$DL/School/Presentations" ;;
    pdf|doc|docx|pages|txt|md)
      if echo "$name" | grep -qiE 'resume|cover.?letter|\bcv\b|portfolio'; then
        mv_safe "$f" "$DL/Career/Docs"
      elif echo "$name" | grep -qiE 'ENTR|ECON|homework|case.?analysis|syllabus|lecture|exam|quiz'; then
        mv_safe "$f" "$DL/School"
      else mv_safe "$f" "$DL/_inbox"; fi ;;
    *)                    mv_safe "$f" "$DL/_needs-review" ;;
  esac
done

INBOX_N=$(find "$DL/_inbox" -maxdepth 1 -type f | wc -l | tr -d ' ')
log ""; log "Moved $moved file(s). _inbox backlog: $INBOX_N item(s)."
echo "Moved $moved file(s). _inbox backlog: $INBOX_N. Log: $LOG"
