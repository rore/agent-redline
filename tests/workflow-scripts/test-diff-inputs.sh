#!/usr/bin/env bash
# tests/workflow-scripts/test-diff-inputs.sh
#
# Tests the "Compute diff inputs" bash block from
# demo-source/.github/workflows/agent-redline.yml. Extracts the block
# via comment fences (ar-test-block: compute-diff-inputs ...
# ar-test-block-end: compute-diff-inputs), then runs it against a
# scratch git repo with mocked SHA inputs.
#
# This catches the bugs we hit during demo standup:
#   - All-zeros BASE_SHA on first push
#   - BASE_SHA referring to a missing commit (force-push)
#   - Normal pair (push event)
#   - Pull-request event
#
# Exit codes:
#   0 — all cases match expected output
#   1 — script error
#   2 — at least one case mismatched

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKFLOW="$REPO_ROOT/demo-source/.github/workflows/agent-redline.yml"

[[ -f "$WORKFLOW" ]] || { echo "error: $WORKFLOW missing" >&2; exit 1; }

# ----------------------------------------------------------------------
# Extract the fenced block.
# Strip the GitHub Actions ${{...}} expressions by replacing them with
# nothing — the block is written so that AR_* env vars override them via
# bash parameter expansion. So when the ${{...}} expression resolves to
# empty, the AR_* default kicks in.
# ----------------------------------------------------------------------

BLOCK_FILE=$(mktemp)
trap 'rm -f "$BLOCK_FILE"' EXIT

awk '
  /# ar-test-block: compute-diff-inputs/ { in_block = 1; next }
  /# ar-test-block-end: compute-diff-inputs/ { in_block = 0; exit }
  in_block { print }
' "$WORKFLOW" > "$BLOCK_FILE"

# Strip the YAML run block indentation (10 spaces in the workflow).
sed -i 's/^          //' "$BLOCK_FILE" 2>/dev/null || sed -i '' 's/^          //' "$BLOCK_FILE"

# Replace ${{ ... }} expressions with empty strings so the AR_* env-var
# defaults take effect.
sed -i 's/\${{[^}]*}}//g' "$BLOCK_FILE" 2>/dev/null || sed -i '' 's/\${{[^}]*}}//g' "$BLOCK_FILE"

if [[ ! -s "$BLOCK_FILE" ]]; then
  echo "error: failed to extract compute-diff-inputs block from $WORKFLOW" >&2
  exit 1
fi

# ----------------------------------------------------------------------
# Set up a scratch git repo with three known commits.
# ----------------------------------------------------------------------

SCRATCH=$(mktemp -d)
trap 'rm -f "$BLOCK_FILE"; rm -rf "$SCRATCH"' EXIT

cd "$SCRATCH"
git init -q -b main
git config user.email "test@example.com"
git config user.name "Test"

echo "v1" > a.txt
git add a.txt
git commit -q -m "initial"
SHA1=$(git rev-parse HEAD)

echo "v2" > a.txt
git add a.txt
git commit -q -m "second"
SHA2=$(git rev-parse HEAD)

echo "v3" > b.txt
git add b.txt
git commit -q -m "third"
SHA3=$(git rev-parse HEAD)

failures=0
ran=0

run_case() {
  local name="$1" event="$2" base="$3" head="$4" expected_files="$5" expected_lines_min="$6"
  ran=$(( ran + 1 ))
  local out_dir="$SCRATCH/out-$ran"
  mkdir -p "$out_dir"
  local gh_output_file="$SCRATCH/github_output_$ran"
  : > "$gh_output_file"

  # The block uses GITHUB_EVENT_NAME and AR_* overrides.
  if ! GITHUB_EVENT_NAME="$event" \
       AR_PR_BASE_SHA="$base" AR_PR_HEAD_SHA="$head" \
       AR_BEFORE_SHA="$base" AR_GH_SHA="$head" \
       AR_OUT_DIR="$out_dir" \
       GITHUB_OUTPUT="$gh_output_file" \
       bash "$BLOCK_FILE" >/dev/null 2>"$out_dir/stderr.log"; then
    echo "FAIL  $name: bash block exited non-zero"
    cat "$out_dir/stderr.log" >&2
    failures=$(( failures + 1 ))
    return
  fi

  local actual_files
  actual_files=$(wc -l < "$out_dir/changed-files.txt" | tr -d ' ')
  if [[ "$actual_files" != "$expected_files" ]]; then
    echo "FAIL  $name: expected $expected_files changed file(s), got $actual_files"
    cat "$out_dir/changed-files.txt" >&2
    failures=$(( failures + 1 ))
    return
  fi

  local lines_changed
  lines_changed=$(grep -oE '[0-9]+' "$gh_output_file" | head -1 || echo 0)
  if (( lines_changed < expected_lines_min )); then
    echo "FAIL  $name: expected lines_changed >= $expected_lines_min, got $lines_changed"
    failures=$(( failures + 1 ))
    return
  fi

  echo "ok    $name (files=$actual_files, lines=$lines_changed)"
}

# ----------------------------------------------------------------------
# Test cases.
# ----------------------------------------------------------------------

# 1. Push event, normal pair.
run_case "push: normal pair" "push" "$SHA2" "$SHA3" 1 1

# 2. Push event, all-zeros base SHA (first push).
run_case "push: all-zeros base SHA" "push" "0000000000000000000000000000000000000000" "$SHA3" 2 2

# 3. Push event, empty base SHA (no `before` field).
run_case "push: empty base SHA" "push" "" "$SHA3" 2 2

# 4. Push event, base SHA refers to a missing commit.
run_case "push: missing-commit base SHA" "push" "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" "$SHA3" 2 2

# 5. Pull-request event, valid base/head.
run_case "pull_request: normal pair" "pull_request" "$SHA1" "$SHA3" 2 2

# 6. Pull-request event, all-zeros base SHA (e.g., from a fresh fork).
run_case "pull_request: all-zeros base SHA" "pull_request" "0000000000000000000000000000000000000000" "$SHA3" 2 2

echo
if (( failures > 0 )); then
  echo "$failures of $ran case(s) failed."
  exit 2
fi
echo "all $ran workflow-block case(s) passed."
