#!/usr/bin/env bash
# BenkiNew: synthetic Bash context checks, no services or data.
set -u
check() {
  local label="$1" code="$2" output status
  output=$(bash -c "$code" 2>&1)
  status=$?
  if [[ "$status" != 0 || "$output" != CONTINUED ]]; then
    printf 'FAIL: %s status=%s output=%s\n' "$label" "$status" "$output" >&2
    return 1
  fi
  printf 'PASS: %s\n' "$label"
}
check function 'f(){ set -e; false; printf "CONTINUED\n"; }; f || printf "HANDLED\n"' || exit 1
check pipefail '(set -e -o pipefail; false; printf "CONTINUED\n") || printf "HANDLED\n"' || exit 1
check outer_if 'if ! (set -e; false; printf "CONTINUED\n"); then printf "HANDLED\n"; fi' || exit 1
check err_trap '(set -eE; trap "printf ERR_TRAP" ERR; false; printf "CONTINUED\n") || printf "HANDLED\n"' || exit 1
