#!/usr/bin/env bash
# tests/scaffold-ci-e2e/check-scaffold-ci-e2e.sh
#
# End-to-end check: extract the push-mode workflow run-block from
# extensions/python/scaffold.md, execute it against a fixture git repo,
# and assert it produces a reporter verdict file.
#
# This catches the class of bug Pallium hit: the structural test
# (tests/scaffold-ci/) confirms the run-block has set +e + EXIT capture
# + the right enforce step, but it doesn't verify the run-block
# ACTUALLY WORKS — that env vars line up with what the bash code
# expects, that the diff invocation produces a file the reporter
# accepts, that the reporter call's flag set is valid.
#
# Strategy:
#   1. Extract the push-mode reporter run-block from scaffold.md.
#   2. Build a minimal fixture: git repo + agent-policy.yaml +
#      vendored reporter + a 2-commit history with a red-zone change.
#   3. Set GITHUB_OUTPUT, github.event.before, github.sha env vars
#      to mimic GitHub Actions, then execute the bash.
#   4. Assert: verdict.json exists, has verdict=RED, GITHUB_OUTPUT has
#      exit_code, run-block exited non-zero.
#
# Exit codes:
#   0 — push-mode workflow run-block executes end-to-end correctly
#   1 — script error (extraction failed, environment missing)
#   2 — workflow run-block produced wrong output

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCAFFOLD="$REPO_ROOT/extensions/python/scaffold.md"
REPORTER="$REPO_ROOT/core/reporter/reporter.py"
EXTRACTOR="$(dirname "${BASH_SOURCE[0]}")/_extract-pushmode.py"

[[ -f "$SCAFFOLD" ]] || { echo "error: scaffold not found" >&2; exit 1; }
[[ -f "$REPORTER" ]] || { echo "error: reporter not found" >&2; exit 1; }
[[ -f "$EXTRACTOR" ]] || { echo "error: extractor not found at $EXTRACTOR" >&2; exit 1; }
command -v python >/dev/null || { echo "error: python not on PATH" >&2; exit 1; }
command -v git >/dev/null || { echo "error: git not on PATH" >&2; exit 1; }

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# ----------------------------------------------------------------------
# Step 1: Extract the push-mode reporter run-block from scaffold.md.
# ----------------------------------------------------------------------

if ! python "$EXTRACTOR" "$SCAFFOLD" > "$TMPDIR/extracted.sh" 2> "$TMPDIR/extract.err"; then
  echo "FAIL: extractor failed:" >&2
  cat "$TMPDIR/extract.err" >&2
  exit 2
fi

if [[ ! -s "$TMPDIR/extracted.sh" ]]; then
  echo "FAIL: extractor produced empty output" >&2
  cat "$TMPDIR/extract.err" >&2
  exit 2
fi

echo "==> step 1: extracted run-block from scaffold.md push-mode example"

# ----------------------------------------------------------------------
# Step 2: Build a minimal fixture.
# ----------------------------------------------------------------------

FIXTURE="$TMPDIR/fixture"
mkdir -p "$FIXTURE/scripts"
cd "$FIXTURE"
git init -q -b main
git config user.email "t@t"
git config user.name "t"

cp "$REPORTER" "$FIXTURE/scripts/agent-redline-report.py"

cat > agent-policy.yaml <<'POLICY_EOF'
version: 1
project:
  name: e2e-fixture
zones:
  red:
    - path: "core/**"
      reason: core layer
      checkpoint: architecture-review
  blue:
    - path: "tests/**"
      reason: tests
checkpoints:
  architecture-review:
    satisfiedBy:
      - codeownerApproval
modes:
  default: shadow
  perCheck:
    boundary_violation: binding
POLICY_EOF

echo "# init" > README.md
git add README.md
git commit -q -m "init"
BEFORE_SHA=$(git rev-parse HEAD)

mkdir -p core
echo "# core change" > core/foo.py
git add core/foo.py
git commit -q -m "edit core/foo.py"
AFTER_SHA=$(git rev-parse HEAD)

echo "==> step 2: fixture built (BEFORE=${BEFORE_SHA:0:8} AFTER=${AFTER_SHA:0:8})"

# ----------------------------------------------------------------------
# Step 3: Substitute GitHub-context expressions.
# ----------------------------------------------------------------------

# Replace `${{ github.event.before }}` and `${{ github.sha }}` with bash vars.
sed -i \
  -e 's|${{ github.event.before }}|$GH_BEFORE|g' \
  -e 's|${{ github.sha }}|$GH_AFTER|g' \
  "$TMPDIR/extracted.sh"

export GITHUB_OUTPUT="$TMPDIR/github_output"
: > "$GITHUB_OUTPUT"
export GH_BEFORE="$BEFORE_SHA"
export GH_AFTER="$AFTER_SHA"

echo "==> step 3: env prepared"

# ----------------------------------------------------------------------
# Step 4: Execute the run-block.
# ----------------------------------------------------------------------

cd "$FIXTURE"
set +e
bash "$TMPDIR/extracted.sh" > "$TMPDIR/run.log" 2>&1
RC=$?
set -e

echo "==> step 4: run-block executed (exit $RC)"

# ----------------------------------------------------------------------
# Step 5: Assertions.
# ----------------------------------------------------------------------

if [[ ! -f "$FIXTURE/build/verdict.json" ]]; then
  echo "FAIL: reporter did not produce build/verdict.json" >&2
  echo "--- run output ---" >&2
  cat "$TMPDIR/run.log" >&2
  exit 2
fi

python - "$FIXTURE/build/verdict.json" <<'ASSERT_EOF'
import json, sys
v = json.load(open(sys.argv[1]))
if "verdict" not in v:
    print("FAIL: verdict.json missing 'verdict' field", file=sys.stderr)
    sys.exit(2)
if v["verdict"] != "RED":
    print(f"FAIL: verdict is {v['verdict']!r}, expected 'RED' (red-zone change to core/foo.py)", file=sys.stderr)
    sys.exit(2)
ASSERT_EOF

if ! grep -q "^exit_code=" "$GITHUB_OUTPUT"; then
  echo "FAIL: GITHUB_OUTPUT missing exit_code=N (the enforce step needs this)" >&2
  cat "$GITHUB_OUTPUT" >&2
  exit 2
fi

# (d) The reporter's exit code (captured into $GITHUB_OUTPUT by the run-block,
# NOT the run-block's overall bash exit, which is intentionally 0 — the
# enforce step is what propagates non-zero) must be non-zero for the red-zone
# change. Specifically: 1 in shadow mode (default), 2 if binding.
CAPTURED_EXIT=$(grep "^exit_code=" "$GITHUB_OUTPUT" | tail -1 | cut -d= -f2)
if [[ "$CAPTURED_EXIT" -eq 0 ]]; then
  echo "FAIL: captured reporter exit_code is 0; red-zone change should produce 1+ (got $CAPTURED_EXIT)" >&2
  cat "$TMPDIR/run.log" >&2
  exit 2
fi

# (e) The run-block itself MUST exit 0 — that's the canonical pattern.
# If it exits non-zero, the sticky-comment / enforce steps in the real
# workflow get skipped under bash -e. This is exactly the bug this test
# is designed to catch.
if [[ "$RC" -ne 0 ]]; then
  echo "FAIL: run-block exited $RC; canonical pattern requires 0 so subsequent steps run" >&2
  cat "$TMPDIR/run.log" >&2
  exit 2
fi

echo "ok: push-mode workflow run-block runs end-to-end"
echo "  - extracted run-block from scaffold.md"
echo "  - executed against a 2-commit fixture (BEFORE/AFTER diff)"
echo "  - reporter produced build/verdict.json with verdict=RED"
echo "  - GITHUB_OUTPUT got exit_code=$CAPTURED_EXIT (the enforce step's input)"
echo "  - run-block exited 0 (canonical: subsequent steps run; enforce gates on exit_code)"
