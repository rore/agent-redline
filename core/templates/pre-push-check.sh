#!/usr/bin/env bash
# scripts/agent-redline-check.sh
#
# Local mirror of the agent-redline CI check.
# Runs the reporter against the local diff (vs the configured base branch)
# and reports the verdict.
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

# Resolve base SHA. If origin isn't fetched, fall back to local main.
if ! BASE_SHA=$(git rev-parse "$BASE_REF" 2>/dev/null); then
  echo "warning: $BASE_REF not found; trying local main" >&2
  BASE_SHA=$(git rev-parse main 2>/dev/null || true)
  if [[ -z "$BASE_SHA" ]]; then
    echo "error: cannot resolve a base ref" >&2
    exit 1
  fi
fi
HEAD_SHA=$(git rev-parse HEAD)

# Locate the reporter. Prefer the project-vendored copy; fall back to a
# system-installed agent-redline if present.
REPORTER=""
if [[ -x "$REPO_ROOT/scripts/agent-redline-report.py" ]]; then
  REPORTER="python $REPO_ROOT/scripts/agent-redline-report.py"
elif command -v agent-redline-report >/dev/null 2>&1; then
  REPORTER="agent-redline-report"
else
  echo "agent-redline reporter not yet installed in this repo." >&2
  echo "TODO: vendor the reporter, or install agent-redline globally." >&2
  exit 0   # Soft success while the reporter is still on the roadmap.
fi

POLICY="$REPO_ROOT/agent-policy.yaml"
if [[ ! -f "$POLICY" ]]; then
  echo "error: $POLICY not found. Run agent-redline bootstrap first." >&2
  exit 1
fi

exec $REPORTER \
  --policy "$POLICY" \
  --base "$BASE_SHA" \
  --head "$HEAD_SHA" \
  --default-mode "${MODE:-shadow}"
