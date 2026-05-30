#!/usr/bin/env bash
# tests/gitignore/check-gitignore.sh
#
# Verifies the .gitignore at the repo root excludes patterns that have
# bitten us before. Catches regressions if someone clears .gitignore
# or forgets a pattern.
#
# Exit codes:
#   0 — all required patterns present
#   2 — at least one missing

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GITIGNORE="$REPO_ROOT/.gitignore"

[[ -f "$GITIGNORE" ]] || { echo "FAIL: $GITIGNORE missing" >&2; exit 2; }

# Patterns we never want to track. Each is a literal substring check on
# the .gitignore file (good enough for these simple cases).
required=(
  ".local/"
  "__pycache__/"
)

missing=()
for pat in "${required[@]}"; do
  if ! grep -qF "$pat" "$GITIGNORE"; then
    missing+=("$pat")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "FAIL: missing required gitignore entries:" >&2
  for m in "${missing[@]}"; do
    echo "  - $m" >&2
  done
  exit 2
fi

# Also verify nothing matching __pycache__ or .local is currently tracked.
cd "$REPO_ROOT"
tracked=$(git ls-files 2>/dev/null | grep -E '__pycache__|^\.local/' || true)
if [[ -n "$tracked" ]]; then
  echo "FAIL: tracked files match patterns that should be ignored:" >&2
  echo "$tracked" >&2
  exit 2
fi

echo "ok    .gitignore has all required entries; no offending files tracked."
