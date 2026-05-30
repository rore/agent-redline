#!/usr/bin/env bash
# tests/budget/check-budget.sh
#
# Walks the budget manifest (tests/budget/budget.yaml) and reports any file
# that exceeds its declared token ceiling. Fails (exit 2) on any breach.
#
# Estimator: approx_tokens = words * 1.33 (rounded up).
#
# Usage:
#   ./tests/budget/check-budget.sh                  # check all
#   ./tests/budget/check-budget.sh --verbose        # show every file with usage %
#
# Exit codes:
#   0 — all files under their ceiling
#   1 — script error (missing manifest, parse failure, etc.)
#   2 — at least one budget breach

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST="$REPO_ROOT/tests/budget/budget.yaml"
VERBOSE=0

for arg in "$@"; do
  case "$arg" in
    --verbose|-v) VERBOSE=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

if [[ ! -f "$MANIFEST" ]]; then
  echo "manifest not found: $MANIFEST" >&2
  exit 1
fi

# Approximate tokens for a file: words * 1.33, rounded up.
estimate_tokens() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "0"
    return
  fi
  local words
  words=$(wc -w < "$file" | tr -d ' ')
  # ceil(words * 1.33) = (words * 133 + 99) / 100
  echo $(( (words * 133 + 99) / 100 ))
}

# Parse budget.yaml without requiring yq/python. The format is intentionally
# simple: each ceiling is three lines (path / max_tokens / why) under "ceilings:".
# This parser does not handle arbitrary YAML — only the specific shape of
# budget.yaml. If the format changes, update this parser.

parse_manifest() {
  local in_ceilings=0
  local cur_path=""
  local cur_max=""
  while IFS= read -r line; do
    if [[ "$line" =~ ^ceilings:[[:space:]]*$ ]]; then
      in_ceilings=1
      continue
    fi
    if (( ! in_ceilings )); then
      continue
    fi
    if [[ "$line" =~ ^[[:space:]]*-[[:space:]]+path:[[:space:]]+(.+)[[:space:]]*$ ]]; then
      # Flush the previous entry
      if [[ -n "$cur_path" && -n "$cur_max" ]]; then
        echo "$cur_path|$cur_max"
      fi
      cur_path="${BASH_REMATCH[1]}"
      cur_max=""
    elif [[ "$line" =~ ^[[:space:]]+max_tokens:[[:space:]]+([0-9]+)[[:space:]]*$ ]]; then
      cur_max="${BASH_REMATCH[1]}"
    fi
  done < "$MANIFEST"
  # Flush the final entry
  if [[ -n "$cur_path" && -n "$cur_max" ]]; then
    echo "$cur_path|$cur_max"
  fi
}

failed=0
checked=0

while IFS='|' read -r pattern ceiling; do
  if [[ -z "$pattern" || -z "$ceiling" ]]; then
    continue
  fi

  # Expand the glob relative to repo root using bash native globbing.
  # Use nullglob locally so an unmatched pattern produces an empty array
  # rather than a literal pattern.
  cd "$REPO_ROOT"
  shopt -s nullglob globstar
  # shellcheck disable=SC2206
  matches=( $pattern )
  shopt -u nullglob globstar

  # Filter to regular files only (skip directories that happened to match)
  filtered=()
  for m in "${matches[@]:-}"; do
    if [[ -f "$REPO_ROOT/$m" ]]; then
      filtered+=("$m")
    fi
  done

  if (( ${#filtered[@]} == 0 )); then
    if (( VERBOSE )); then
      echo "  (no files match: $pattern)"
    fi
    continue
  fi

  for relpath in "${filtered[@]}"; do
    full="$REPO_ROOT/$relpath"
    tokens=$(estimate_tokens "$full")
    pct=$(( tokens * 100 / ceiling ))
    checked=$(( checked + 1 ))

    if (( tokens > ceiling )); then
      printf "FAIL  %-60s %5d / %5d tokens (%d%%)\n" "$relpath" "$tokens" "$ceiling" "$pct"
      failed=$(( failed + 1 ))
    elif (( VERBOSE )); then
      printf "ok    %-60s %5d / %5d tokens (%d%%)\n" "$relpath" "$tokens" "$ceiling" "$pct"
    fi
  done
done < <(parse_manifest)

echo
if (( failed > 0 )); then
  echo "$failed of $checked file(s) over budget."
  exit 2
fi
echo "all $checked file(s) within budget."
exit 0
