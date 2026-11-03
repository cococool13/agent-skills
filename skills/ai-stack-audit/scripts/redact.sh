#!/bin/bash
# redact.sh - shared redaction filter for every ai-stack-audit script. stdin -> stdout.
#
# Masks: sk-ant-..., other sk-/sk_live_ keys, ghp_/gho_/ghu_/ghs_/ghr_/github_pat_, AKIA...,
# xox[abposr]-..., "Bearer ...", PEM private-key blocks, JWTs, key|token|secret|password = value,
# 32+ char hex runs, and 32+ char base64-like runs with high entropy.
# Keeps: 16-hex fingerprints/hash prefixes, file paths, names, counts.
#
# Allowlisted commands: perl (system /usr/bin/perl, read stdin only), cat, mktemp, grep.
# Writes nothing. Exit 0 always in filter mode.
#
# Usage:  some-command | redact.sh
#         redact.sh --selftest
set -euo pipefail

PERL_PROG='
use strict; use warnings;
sub entropy { my ($s)=@_; my %c; $c{$_}++ for split //, $s; my $n=length $s; my $h=0;
  for (values %c) { my $p=$_/$n; $h -= $p*log($p)/log(2) } return $h }
sub longrun { my ($s)=@_;
  my $u = $s; $u =~ s/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}//g;
  if ($u ne $s) { return $s if length($u) < 32 || $u !~ /[0-9]/ || entropy($u) < 4.2; return longrun($u) eq $u ? $s : "<redacted:b64>" }
  return "<redacted:hex>" if $s =~ /^[0-9a-fA-F]{32,}$/ && $s =~ /[0-9]/ && $s =~ /[a-fA-F]/;
  return "<redacted:b64>" if $s =~ /[0-9]/ && $s =~ /[A-Za-z]/ && entropy($s) >= 4.2;
  return $s }
my $inpem = 0;
while (my $l = <STDIN>) {
  if ($l =~ /-----BEGIN [A-Z ]*PRIVATE KEY-----/) { $inpem = 1; print "<redacted:pem>\n"; next }
  if ($inpem) { $inpem = 0 if $l =~ /-----END [A-Z ]*PRIVATE KEY-----/; next }
  $l =~ s/sk-ant-[A-Za-z0-9_\-]+/sk-ant-<redacted>/g;
  $l =~ s/\bsk-(?:proj-)?[A-Za-z0-9_\-]{16,}/sk-<redacted>/g;
  $l =~ s/\b(sk|pk|rk)_(live|test)_[A-Za-z0-9]{8,}/$1_$2_<redacted>/g;
  $l =~ s/\b(gh[pousr])_[A-Za-z0-9]{10,}/$1_<redacted>/g;
  $l =~ s/\bgithub_pat_[A-Za-z0-9_]{10,}/github_pat_<redacted>/g;
  $l =~ s/\b(AKIA|ASIA)[0-9A-Z]{12,}/$1<redacted>/g;
  $l =~ s/\bxox([abposr])-[A-Za-z0-9\-]{6,}/xox$1-<redacted>/g;
  $l =~ s/\b(Bearer|Basic)\s+[A-Za-z0-9._~+\/=\-]{6,}/$1 <redacted>/gi;
  $l =~ s/\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}(?:\.[A-Za-z0-9_\-]+)?/<redacted:jwt>/g;
  $l =~ s/((?:api[_-]?)?(?:key|token|secret|passwd|password|pwd|auth)[A-Za-z0-9_\-]*["\x27]?\s*[=:]\s*["\x27]?)([^"\x27\s,;&}\]]{8,})/$1<redacted>/gi;
  $l =~ s/([A-Za-z0-9+\/=_\-]{32,})/longrun($1)/ge;
  print $l;
}'

filter() { /usr/bin/perl -e "$PERL_PROG"; }

if [[ "${1:-}" == "--selftest" ]]; then
  # Fake values built from pieces so this file itself never holds a full secret-shaped literal.
  A="sk-ant-api03-""SELFTESTxxxxxxxxxxxxxxxxxxxxxxxxxxxx1234"
  G="ghp_""ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
  P="github_pat_""11ABCDEFG0123456789_abcdefghijklmnop"
  K="AKIA""IOSFODNN7EXAMPLE"
  S="xoxb-""123456789012-abcdefghijkl"
  B="Bearer ""abc.DEF-ghi_jkl123456"
  E="MY_API_KEY=""supersecretvalue123"
  H="0123456789abcdef0123456789abcdef0123"
  R="Zm9vYmFy""QmF6UXV4MTIzNDU2Nzg5MEFCQ0RFRkdISUpL"
  J="eyJhbGciOi""JIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl"
  KEEP1="fingerprint=6398a1b2c3d4e5f6"
  KEEP2="/Users/cococool/Library/LaunchAgents/com.cococool.skills-update.plist"
  KEEP3='"settings_env_keys": 17, "env_key_names": ["GEMINI_API_KEY","STITCH_API_KEY"]'
  KEEP4="-Users-cococool-Projects--review-ai-stack-audit-2026-10-19"
  KEEP5="mcp__29535def-881b-4d10-a8a7-838ea98798ca__get_equity_tax_lots"
  in=$(printf '%s\n' "$A" "$G" "$P" "$K" "$S" "$B" "$E" "$H" "$R" "$J" "$KEEP1" "$KEEP2" "$KEEP3" "$KEEP4" "$KEEP5" \
    "-----BEGIN OPENSSH PRIVATE KEY-----" "c2VjcmV0" "-----END OPENSSH PRIVATE KEY-----")
  out=$(printf '%s\n' "$in" | filter)
  rc=0
  for bad in SELFTESTxxxx ABCDEFGHIJKLMNOPQRSTUVWXYZ0123 11ABCDEFG IOSFODNN7 123456789012-abc abc.DEF-ghi \
             supersecretvalue 0123456789abcdef0123456789abcdef QmF6UXV4 JIUzI1NiJ9 c2VjcmV0; do
    if grep -q -- "$bad" <<<"$out"; then echo "FAIL leaked: ${bad:0:6}..."; rc=1; fi
  done
  for keep in "$KEEP1" "$KEEP2" "$KEEP3" "$KEEP4" "$KEEP5"; do
    if ! grep -qF -- "$keep" <<<"$out"; then echo "FAIL over-redacted: ${keep:0:40}"; rc=1; fi
  done
  [[ $rc -eq 0 ]] && echo "redact.sh selftest PASS (11 masks, 5 keeps)" || echo "redact.sh selftest FAIL"
  exit $rc
fi

filter
