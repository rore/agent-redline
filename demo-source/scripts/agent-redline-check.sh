#!/usr/bin/env bash
# scripts/agent-redline-check.sh
#
# Runs the vendored agent-redline reporter against the local diff and
# prints the verdict. Mirrors what CI runs.
#
# Usage:
#   ./scripts/agent-redline-check.sh                    # against origin/main
#   ./scripts/agent-redline-check.sh --base develop     # different base

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
BASE_REF="origin/main"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) BASE_REF="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

if ! BASE_SHA=$(git rev-parse "$BASE_REF" 2>/dev/null); then
  echo "warning: $BASE_REF not found; trying local main" >&2
  BASE_SHA=$(git rev-parse main 2>/dev/null || true)
  if [[ -z "$BASE_SHA" ]]; then
    echo "error: cannot resolve a base ref" >&2
    exit 1
  fi
fi
HEAD_SHA=$(git rev-parse HEAD)

POLICY="$REPO_ROOT/agent-policy.yaml"
[[ -f "$POLICY" ]] || { echo "error: $POLICY not found" >&2; exit 1; }

REPORTER="$REPO_ROOT/scripts/agent-redline-report.py"
[[ -x "$REPORTER" ]] || REPORTER="python $REPO_ROOT/scripts/agent-redline-report.py"

# Build the changed-files list and line-count from git diff.
CHANGED_FILES=$(mktemp)
trap 'rm -f "$CHANGED_FILES"' EXIT
git diff --name-only "$BASE_SHA"..."$HEAD_SHA" > "$CHANGED_FILES"
LINES_CHANGED=$(git diff --shortstat "$BASE_SHA"..."$HEAD_SHA" | grep -oE '[0-9]+ insertion' | head -1 | grep -oE '[0-9]+' || echo 0)
LINES_CHANGED_DEL=$(git diff --shortstat "$BASE_SHA"..."$HEAD_SHA" | grep -oE '[0-9]+ deletion' | head -1 | grep -oE '[0-9]+' || echo 0)
LINES_CHANGED=$((${LINES_CHANGED:-0} + ${LINES_CHANGED_DEL:-0}))

# ArchUnit XML if the build produced one.
ARCHUNIT_XML=""
if compgen -G "$REPO_ROOT/build/test-results/test/TEST-*ArchitectureTest*.xml" > /dev/null; then
  ARCHUNIT_XML=$(ls "$REPO_ROOT"/build/test-results/test/TEST-*ArchitectureTest*.xml | head -1)
fi

ARGS=(--policy "$POLICY" --changed-files "$CHANGED_FILES" --lines-changed "$LINES_CHANGED" --mode "${MODE:-shadow}")
if [[ -n "$ARCHUNIT_XML" ]]; then
  ARGS+=(--archunit-xml "$ARCHUNIT_XML")
fi

exec $REPORTER "${ARGS[@]}"
