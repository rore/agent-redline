#!/usr/bin/env bash
# tests/sync/test-sync-demo.sh
#
# Runs scripts/sync-demo.sh against a temporary git repo and verifies
# the result has the expected structure. Catches regressions in the
# sync logic without requiring a real GitHub repo.
#
# Verifies:
#   - sync-demo.sh runs without error against a fresh empty git repo
#   - The greenfield branch contains the Spring source but NO agent-redline artifacts
#   - The main branch contains both Spring source AND agent-redline artifacts
#   - Each PR-scenario branch exists and differs from main
#   - The vendored reporter is present and matches core/reporter/reporter.py
#
# Exit codes:
#   0 — all checks pass
#   1 — script error
#   2 — sync produced unexpected output

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SYNC_SCRIPT="$REPO_ROOT/scripts/sync-demo.sh"
[[ -x "$SYNC_SCRIPT" ]] || { echo "error: $SYNC_SCRIPT missing" >&2; exit 1; }

SCRATCH=$(mktemp -d)
trap 'rm -rf "$SCRATCH"' EXIT

cd "$SCRATCH"
git init -q -b main
git config user.email "test@example.com"
git config user.name "Test"
# An empty repo doesn't have a HEAD until the first commit; sync-demo.sh
# expects a real .git/. We just need it to be a valid git directory.
echo "placeholder" > .placeholder
git add .placeholder
git commit -q -m "init"

failures=0

assert_file_exists() {
  if [[ ! -f "$1" ]]; then
    echo "FAIL  expected file: $1"
    failures=$(( failures + 1 ))
  fi
}

assert_file_missing() {
  if [[ -f "$1" ]]; then
    echo "FAIL  expected file MISSING but present: $1"
    failures=$(( failures + 1 ))
  fi
}

assert_branch_exists() {
  if ! git -C "$SCRATCH" rev-parse --verify "$1" >/dev/null 2>&1; then
    echo "FAIL  expected branch: $1"
    failures=$(( failures + 1 ))
  fi
}

# ----------------------------------------------------------------------
# Run sync-demo (without --push).
# ----------------------------------------------------------------------

echo "==> running sync-demo against $SCRATCH"
if ! bash "$SYNC_SCRIPT" --target "$SCRATCH" --with-pr-branches >/tmp/sync-demo.log 2>&1; then
  echo "FAIL  sync-demo.sh exited non-zero"
  cat /tmp/sync-demo.log >&2
  exit 2
fi

# ----------------------------------------------------------------------
# Check greenfield branch.
# ----------------------------------------------------------------------

echo "==> checking greenfield branch"
git -C "$SCRATCH" checkout -q greenfield
assert_file_exists "$SCRATCH/build.gradle"
assert_file_exists "$SCRATCH/src/main/java/com/example/orders/domain/Order.java"
assert_file_exists "$SCRATCH/src/test/java/com/example/orders/architecture/DependencyArchitectureTest.java"
assert_file_missing "$SCRATCH/agent-policy.yaml"
assert_file_missing "$SCRATCH/AGENTS.md"
assert_file_missing "$SCRATCH/scripts/agent-redline-report.py"
assert_file_missing "$SCRATCH/.github/workflows/agent-redline.yml"

# ----------------------------------------------------------------------
# Check main branch.
# ----------------------------------------------------------------------

echo "==> checking main branch"
git -C "$SCRATCH" checkout -q main
assert_file_exists "$SCRATCH/build.gradle"
assert_file_exists "$SCRATCH/src/main/java/com/example/orders/domain/Order.java"
assert_file_exists "$SCRATCH/agent-policy.yaml"
assert_file_exists "$SCRATCH/AGENTS.md"
assert_file_exists "$SCRATCH/CODEOWNERS"
assert_file_exists "$SCRATCH/scripts/agent-redline-check.sh"
assert_file_exists "$SCRATCH/scripts/agent-redline-report.py"
assert_file_exists "$SCRATCH/.github/workflows/agent-redline.yml"
assert_file_exists "$SCRATCH/.github/pull_request_template.md"
assert_file_exists "$SCRATCH/docs/agent/blue-zone-work.md"
assert_file_exists "$SCRATCH/docs/agent/red-zone-change.md"
assert_file_exists "$SCRATCH/docs/agent/gray-zone-change.md"
assert_file_exists "$SCRATCH/docs/agent/boundary-violation.md"
assert_file_exists "$SCRATCH/docs/agent/pr-discipline.md"

# Verify the vendored reporter matches the source (line-ending agnostic).
if ! diff -q --strip-trailing-cr "$REPO_ROOT/core/reporter/reporter.py" "$SCRATCH/scripts/agent-redline-report.py" >/dev/null; then
  echo "FAIL  vendored reporter does not match source"
  failures=$(( failures + 1 ))
fi

# ----------------------------------------------------------------------
# Check PR-scenario branches.
# ----------------------------------------------------------------------

for branch in demo/blue-only-pr demo/red-with-checkpoint-pr demo/boundary-violation-pr; do
  echo "==> checking $branch"
  assert_branch_exists "$branch"
  if git -C "$SCRATCH" rev-parse --verify "$branch" >/dev/null 2>&1; then
    main_sha=$(git -C "$SCRATCH" rev-parse main)
    branch_sha=$(git -C "$SCRATCH" rev-parse "$branch")
    if [[ "$main_sha" == "$branch_sha" ]]; then
      echo "FAIL  $branch == main (apply.sh produced no diff)"
      failures=$(( failures + 1 ))
    fi
  fi
done

# ----------------------------------------------------------------------
# Done.
# ----------------------------------------------------------------------

echo
if (( failures > 0 )); then
  echo "$failures sync check(s) failed."
  exit 2
fi
echo "all sync checks passed."
