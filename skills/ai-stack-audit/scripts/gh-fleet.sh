#!/bin/bash
# gh-fleet.sh - GET-only GitHub fleet snapshot. Writes <out>/gh-fleet.json.
#
# Per repo: visibility, archived, pushedAt, default branch, branch protection present, ruleset count,
# Dependabot alerts enabled, open Dependabot alerts by severity, branch count.
#
# Read-only by construction. Allowlisted commands: `gh repo list`, `gh api <path>` (GET only:
# no method flag, no field flags, no input flag; the selftest greps this file to prove it),
# jq, date, mktemp. Never selects secret-scanning fields. All output goes through redact.sh.
# Cost: about 5 API calls per repo (57 repos ~ 290 calls of the 5000/h core limit).
#
# Usage: gh-fleet.sh [--owner cococool13] [--out DIR] [--limit 300]
#        gh-fleet.sh --selftest
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDACT="$HERE/redact.sh"
OWNER="cococool13"
OUT="."
LIMIT=300

selftest() {
  local t rc=0; t="$(mktemp -d)"
  trap 'rm -rf "$t"' RETURN
  # 1. static proof: no mutating flag on any gh call in this file
  local m='-''X|--''method|-''f |-''F |--''field|--''raw-field|--''input'
  local bad; bad="$(grep -nE '(^|[^A-Za-z_-])gh (api|repo|pr|issue|release|secret|variable|workflow)' "$0" \
    | grep -E -- "( |=)($m)" || true)"
  if [[ -n "$bad" ]]; then echo "FAIL mutating flag on a gh call:"; echo "$bad"; rc=1; else echo "ok no mutating gh flags (self-grep)"; fi
  if grep -nE '(^|[^A-Za-z_-])gh (repo (edit|archive|delete|create|rename)|pr (merge|close)|issue (close|create)|secret set)' "$0" | grep -v 'grep -nE' >/dev/null; then
    echo "FAIL mutating gh subcommand present"; rc=1; else echo "ok no mutating gh subcommands"; fi
  # 2. fixture run through a stub gh that logs argv and serves fixtures
  mkdir -p "$t/bin" "$t/out"
  cat > "$t/bin/gh" <<'STUB'
#!/bin/bash
echo "$*" >> "$GH_STUB_LOG"
fx="$GH_FIXTURES"; jqx=""; silent=0; path=""; sub="$1 ${2:-}"
args=("$@"); i=0
while [[ $i -lt ${#args[@]} ]]; do
  a="${args[$i]}"
  case "$a" in
    --jq) i=$((i+1)); jqx="${args[$i]}" ;;
    --silent) silent=1 ;;
    --paginate) ;;
    repos/*) path="$a" ;;
  esac
  i=$((i+1))
done
if [[ "$sub" == "repo list" ]]; then f="$fx/repos.json"
else f="$fx/$(printf '%s' "$path" | sed -E 's#[/?&=]#_#g').json"; fi
[[ -f "$f" ]] || { echo "gh: Not Found (HTTP 404)" >&2; exit 1; }
[[ $silent -eq 1 ]] && exit 0
if [[ -n "$jqx" ]]; then jq -r "$jqx" "$f"; else cat "$f"; fi
STUB
  chmod +x "$t/bin/gh"
  GH_STUB_LOG="$t/argv.log" GH_FIXTURES="$HERE/fixtures/gh-fleet" PATH="$t/bin:$PATH" \
    "$0" --owner o --out "$t/out" >/dev/null
  local j="$t/out/gh-fleet.json"
  chk() { local got; got="$(jq -cS "$1" "$j")"; if [[ "$got" == "$2" ]]; then echo "ok $1"; else echo "FAIL $1 got=$got want=$2"; rc=1; fi; }
  chk '.repos|length' '2'
  chk '.repos[0].branch_protection' 'true'
  chk '.repos[0].rulesets' '1'
  chk '.repos[0].dependabot_alerts_enabled' 'true'
  chk '.repos[0].open_alerts' '{"critical":1,"high":2,"low":0,"medium":0}'
  chk '.repos[0].branches' '2'
  chk '.repos[1].archived' 'true'
  chk '.repos[1].branch_protection' 'false'
  chk '.repos[1].dependabot_alerts_enabled' 'false'
  chk '.repos[1].open_alerts' 'null'
  chk '.totals' '{"archived":1,"branch_protection":1,"dependabot_alerts_enabled":1,"open_alerts":{"critical":1,"high":2,"low":0,"medium":0},"public":1,"repos":2}'
  # 3. dynamic proof: every argv the stub saw is a GET-shaped call
  if grep -vE '^(repo list|api) ' "$t/argv.log" | grep -q .; then echo "FAIL non-read gh subcommand called"; rc=1; fi
  if grep -qE -- "( |^)($m)" "$t/argv.log"; then echo "FAIL mutating flag passed to gh"; rc=1; else echo "ok stub saw $(wc -l < "$t/argv.log" | tr -d ' ') GET-only calls"; fi
  [[ $rc -eq 0 ]] && echo "gh-fleet.sh selftest PASS" || echo "gh-fleet.sh selftest FAIL"
  return $rc
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --selftest) selftest; exit $? ;;
    --owner) OWNER="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
mkdir -p "$OUT"
ROWS="$(mktemp "${TMPDIR:-/tmp}/ghf.XXXXXX")"
trap 'rm -f "$ROWS"' EXIT

gh repo list "$OWNER" --limit "$LIMIT" --json name,visibility,isArchived,pushedAt,defaultBranchRef \
  | jq -c '.[] | {name, visibility, archived: .isArchived, pushed_at: .pushedAt, default_branch: (.defaultBranchRef.name // null)}' \
  | while IFS= read -r row; do
  name="$(jq -r .name <<<"$row")"; br="$(jq -r '.default_branch // empty' <<<"$row")"
  prot=false
  [[ -n "$br" ]] && gh api "repos/$OWNER/$name/branches/$br/protection" --silent >/dev/null 2>&1 && prot=true
  rules="$(gh api "repos/$OWNER/$name/rulesets" --jq 'length' 2>/dev/null || true)"; [[ "$rules" =~ ^[0-9]+$ ]] || rules=null
  dep=false; gh api "repos/$OWNER/$name/vulnerability-alerts" --silent >/dev/null 2>&1 && dep=true
  alerts=null
  if sev="$(gh api --paginate "repos/$OWNER/$name/dependabot/alerts?state=open&per_page=100" --jq '.[].security_advisory.severity' 2>/dev/null)"; then
    alerts="$(printf '%s\n' "$sev" | jq -Rsc 'split("\n")|map(select(length>0)|ascii_downcase) as $s
      | {critical: ($s|map(select(.=="critical"))|length), high: ($s|map(select(.=="high"))|length),
         medium: ($s|map(select(.=="medium" or .=="moderate"))|length), low: ($s|map(select(.=="low"))|length)}')"
  fi
  nbr="$(gh api --paginate "repos/$OWNER/$name/branches?per_page=100" --jq '.[].name' 2>/dev/null | grep -c . || true)"
  jq -c --argjson p "$prot" --argjson r "${rules:-null}" --argjson d "$dep" --argjson a "$alerts" --argjson b "${nbr:-0}" \
    '. + {branch_protection: $p, rulesets: $r, dependabot_alerts_enabled: $d, open_alerts: $a, branches: $b}' <<<"$row" >> "$ROWS"
done

jq -s --arg owner "$OWNER" --arg gen "$(date '+%Y-%m-%d %H:%M %Z')" '{
  owner: $owner, generated: $gen, repos: .,
  totals: {repos: length, archived: (map(select(.archived))|length), public: (map(select(.visibility=="PUBLIC"))|length),
           branch_protection: (map(select(.branch_protection))|length),
           dependabot_alerts_enabled: (map(select(.dependabot_alerts_enabled))|length),
           open_alerts: (reduce (map(.open_alerts // {})[]) as $a ({critical:0,high:0,medium:0,low:0};
             .critical += ($a.critical//0) | .high += ($a.high//0) | .medium += ($a.medium//0) | .low += ($a.low//0)))}}' "$ROWS" \
  | "$REDACT" > "$OUT/gh-fleet.json"
jq -c .totals "$OUT/gh-fleet.json"
