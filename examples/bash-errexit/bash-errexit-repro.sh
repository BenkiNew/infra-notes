#!/usr/bin/env bash
# Author: XAKERBANK (BenkiNew) — https://github.com/BenkiNew
# Synthetic example: no files, credentials, network or service operations.
set -u
legacy() {
  (set -e
    false
    printf 'UNCHANGED (misleading)\n'
  ) || return 1
}
fixed() {
  (
    if ! false; then
      printf 'Generation failed\n' >&2
      exit 1
    fi
    printf 'UNCHANGED\n'
  ) || return 1
}
legacy
legacy_status=$?
fixed
fixed_status=$?
printf 'legacy=%s fixed=%s\n' "$legacy_status" "$fixed_status"
[[ "$legacy_status" == 0 && "$fixed_status" == 1 ]]
