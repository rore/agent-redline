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
#
# Notes on api.type: openapi-from-controllers
#   The CI workflow generates spec_base.yaml + spec_head.yaml at the two
#   SHAs and passes them to the reporter. This local check does NOT run
#   the generation command (running two builds during a pre-push is
#   hostile). Instead it relies on red-zone path classification — touched
#   controllers are red and trigger api-review via the policy. The CI run
#   sees the structural diff; the local run sees "you touched a controller."
#   That asymmetry is by design.

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
if [[ -x "$REPO_ROOT/scripts/agent-redline-report.py" ]] || \
   [[ -f "$REPO_ROOT/scripts/agent-redline-report.py" ]]; then
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

# Compute the changed-files list and total lines changed.
CHANGED_FILES_LIST="$(mktemp)"
trap 'rm -f "$CHANGED_FILES_LIST"' EXIT
git diff --name-only "$BASE_SHA"..."$HEAD_SHA" > "$CHANGED_FILES_LIST"
LINES_CHANGED=$(git diff --shortstat "$BASE_SHA"..."$HEAD_SHA" \
  | awk '{for (i=1;i<=NF;i++) if ($i ~ /insertions?|deletions?/) s+=$(i-1); print s+0}')

# Optional: if the build produced an ArchUnit JUnit XML, surface it.
ARCHUNIT_ARG=""
ARCHUNIT_XML="$REPO_ROOT/build/test-results/test/TEST-*ArchitectureTest.xml"
for f in $ARCHUNIT_XML; do
  if [[ -f "$f" ]]; then
    ARCHUNIT_ARG="--archunit-xml $f"
    break
  fi
done

exec $REPORTER \
  --policy "$POLICY" \
  --changed-files "$CHANGED_FILES_LIST" \
  --lines-changed "$LINES_CHANGED" \
  $ARCHUNIT_ARG \
  --default-mode "${MODE:-shadow}"
