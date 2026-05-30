#!/usr/bin/env bash
# tests/package/check-package.sh
#
# Drift check: rebuilds the package into a temp directory, then compares
# against the committed dist/agent-redline/. If they differ, someone
# changed source-of-truth files without re-running scripts/package-skill.sh.
#
# Exit codes:
#   0 — package is up to date with sources
#   1 — script error
#   2 — drift detected (run scripts/package-skill.sh and commit the result)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST="$REPO_ROOT/dist/agent-redline"

[[ -d "$DIST" ]] || { echo "error: $DIST missing — run scripts/package-skill.sh first" >&2; exit 1; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

bash "$REPO_ROOT/scripts/package-skill.sh" --dest "$TMP/agent-redline" >/dev/null

# Compare every file. Ignore .package-source-rev (it's just a HEAD marker
# and will differ during rebuilds).
DIFF_OUTPUT=$(diff -r --exclude='.package-source-rev' --strip-trailing-cr "$DIST" "$TMP/agent-redline" 2>&1 || true)

if [[ -n "$DIFF_OUTPUT" ]]; then
  echo "FAIL: dist/agent-redline/ is out of sync with sources." >&2
  echo "Run scripts/package-skill.sh and commit the result." >&2
  echo
  echo "Diff (truncated to 100 lines):" >&2
  echo "$DIFF_OUTPUT" | head -100 >&2
  exit 2
fi

echo "ok: dist/agent-redline/ matches sources."
