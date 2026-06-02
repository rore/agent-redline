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

if ! python "$EXTRACTOR" "$SCAFFOLD" --reporter > "$TMPDIR/extracted.sh" 2> "$TMPDIR/extract.err"; then
  echo "FAIL: extractor failed:" >&2
  cat "$TMPDIR/extract.err" >&2
  exit 2
fi

if [[ ! -s "$TMPDIR/extracted.sh" ]]; then
  echo "FAIL: extractor produced empty output" >&2
  cat "$TMPDIR/extract.err" >&2
  exit 2
fi

# Also extract the summary step — separate `run: |` block in the same
# yaml block, executed by the workflow as its own step. We run it
# after the reporter step to verify the visibility surface works.
if ! python "$EXTRACTOR" "$SCAFFOLD" --summary > "$TMPDIR/extracted-summary.sh" 2> "$TMPDIR/summary-extract.err"; then
  echo "FAIL: summary-step extractor failed:" >&2
  cat "$TMPDIR/summary-extract.err" >&2
  exit 2
fi

# Also extract the Check Run step — posts to /check-runs via gh api.
# We mock `gh api` and `jq` is already on PATH for the JSON build.
if ! python "$EXTRACTOR" "$SCAFFOLD" --check-run > "$TMPDIR/extracted-check-run.sh" 2> "$TMPDIR/check-run-extract.err"; then
  echo "FAIL: check-run step extractor failed:" >&2
  cat "$TMPDIR/check-run-extract.err" >&2
  exit 2
fi

echo "==> step 1: extracted reporter + summary + check-run run-blocks from scaffold.md"

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

# The check-run step references several github-context expressions and
# `steps.report.outputs.exit_code`. Replace them all with bash vars so
# the script runs in plain bash. We also point `gh` at a mock that
# captures the API call payload to a file we can inspect.
sed -i \
  -e 's|${{ steps.report.outputs.exit_code }}|$REPORT_EXIT|g' \
  -e 's|${{ github.server_url }}|$GH_SERVER_URL|g' \
  -e 's|${{ github.repository }}|$GH_REPOSITORY|g' \
  -e 's|${{ github.run_id }}|$GH_RUN_ID|g' \
  -e 's|${{ github.sha }}|$GH_AFTER|g' \
  -e 's|${{ secrets.GITHUB_TOKEN }}|$GH_TOKEN_FAKE|g' \
  "$TMPDIR/extracted-check-run.sh"

export GITHUB_OUTPUT="$TMPDIR/github_output"
: > "$GITHUB_OUTPUT"
# GITHUB_STEP_SUMMARY: the run-block's "Write verdict to job summary"
# step appends comment.md here. We assert below that this file ends up
# containing the verdict, since it's the primary visibility surface in
# push-mode (no PR sticky comment).
export GITHUB_STEP_SUMMARY="$TMPDIR/github_step_summary.md"
: > "$GITHUB_STEP_SUMMARY"
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

# Execute the summary step in the same fixture (mirrors what GitHub
# Actions does: run each step in order, sharing the GITHUB_STEP_SUMMARY
# env var that points at a per-job append-only file).
set +e
bash "$TMPDIR/extracted-summary.sh" > "$TMPDIR/summary-run.log" 2>&1
SUMMARY_RC=$?
set -e
if [[ "$SUMMARY_RC" -ne 0 ]]; then
  echo "FAIL: summary step exited $SUMMARY_RC" >&2
  cat "$TMPDIR/summary-run.log" >&2
  exit 2
fi

echo "==> step 4b: summary step executed (exit $SUMMARY_RC)"

# ----------------------------------------------------------------------
# Step 4c: Execute the Check Run step under three reporter exits — verify
# it maps 0/1/2 to success/action_required/failure conclusions. We mock
# `gh api` with a shim that captures the JSON payload to a file so we
# can introspect it without hitting the network.
# ----------------------------------------------------------------------
#
# Requires `jq` (which the canonical scaffold uses to build the API
# payload). On systems without jq we still run the static shape check
# above; only the live execution is skipped.
if ! command -v jq >/dev/null 2>&1; then
  echo "==> step 4c: jq not on PATH; skipping Check Run live-execution layer"
  echo "          (the static check covers the structural pattern; jq is on"
  echo "           the canonical GitHub Actions ubuntu-latest image)"
else
  GH_SHIM_DIR="$TMPDIR/bin"
  mkdir -p "$GH_SHIM_DIR"
  cat > "$GH_SHIM_DIR/gh" <<'GH_SHIM_EOF'
#!/usr/bin/env bash
# Mock `gh` for the e2e test. Captures the --input file's JSON contents
# next to the calling test's TMPDIR for assertion. Accepts the canonical
# argv shape: `gh api --method POST -H ... <endpoint> --input <file>`.
INPUT_FILE=""
ENDPOINT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --input) INPUT_FILE="$2"; shift 2 ;;
    --method|-H) shift 2 ;;
    /*) ENDPOINT="$1"; shift ;;
    *) shift ;;
  esac
done
if [[ -n "$INPUT_FILE" && -f "$INPUT_FILE" ]]; then
  cp "$INPUT_FILE" "$GH_MOCK_CAPTURE"
fi
echo "GH_MOCK: endpoint=$ENDPOINT input=$INPUT_FILE" >> "$GH_MOCK_LOG"
GH_SHIM_EOF
  chmod +x "$GH_SHIM_DIR/gh"

  # Tee variables the check-run step reads.
  export GH_SERVER_URL="https://github.com"
  export GH_REPOSITORY="example-org/example-repo"
  export GH_RUN_ID="999999"
  export GH_TOKEN_FAKE="fake-token"
  export GH_MOCK_LOG="$TMPDIR/gh-mock.log"
  : > "$GH_MOCK_LOG"

  # Run the check-run step three times: once with each EXIT in {0,1,2}.
  # For each, assert the captured JSON's `conclusion` field equals the
  # expected mapping.
  declare -A EXPECTED=( [0]="success" [1]="action_required" [2]="failure" )
  for EXIT_VAL in 0 1 2; do
    export REPORT_EXIT="$EXIT_VAL"
    export GH_MOCK_CAPTURE="$TMPDIR/check-run-payload-$EXIT_VAL.json"

    # The check-run step assumes `build/comment.md` and `build/verdict.json`
    # exist (created by the reporter step earlier). They do — the reporter
    # ran with EXIT 1 above.
    PATH="$GH_SHIM_DIR:$PATH" bash "$TMPDIR/extracted-check-run.sh" \
      > "$TMPDIR/check-run-$EXIT_VAL.log" 2>&1
    CR_RC=$?
    if [[ "$CR_RC" -ne 0 ]]; then
      echo "FAIL: check-run step exited $CR_RC for EXIT=$EXIT_VAL" >&2
      cat "$TMPDIR/check-run-$EXIT_VAL.log" >&2
      exit 2
    fi
    if [[ ! -f "$GH_MOCK_CAPTURE" ]]; then
      echo "FAIL: check-run step did not call \`gh api\` (no payload captured for EXIT=$EXIT_VAL)" >&2
      cat "$TMPDIR/check-run-$EXIT_VAL.log" >&2
      exit 2
    fi
    GOT_CONCLUSION=$(jq -r '.conclusion' "$GH_MOCK_CAPTURE")
    EXPECTED_CONCLUSION="${EXPECTED[$EXIT_VAL]}"
    if [[ "$GOT_CONCLUSION" != "$EXPECTED_CONCLUSION" ]]; then
      echo "FAIL: EXIT=$EXIT_VAL produced conclusion=$GOT_CONCLUSION, expected $EXPECTED_CONCLUSION" >&2
      cat "$GH_MOCK_CAPTURE" >&2
      exit 2
    fi
    # Also assert the payload has the required shape.
    HEAD_SHA=$(jq -r '.head_sha' "$GH_MOCK_CAPTURE")
    if [[ "$HEAD_SHA" != "$AFTER_SHA" ]]; then
      echo "FAIL: head_sha=$HEAD_SHA != AFTER_SHA=$AFTER_SHA" >&2
      exit 2
    fi
    DETAILS_URL=$(jq -r '.details_url' "$GH_MOCK_CAPTURE")
    if [[ "$DETAILS_URL" != "$GH_SERVER_URL/$GH_REPOSITORY/actions/runs/$GH_RUN_ID" ]]; then
      echo "FAIL: details_url=$DETAILS_URL doesn't match expected run URL" >&2
      exit 2
    fi
  done
  echo "==> step 4c: check-run step maps {0,1,2} -> {success, action_required, failure} correctly"
fi

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

if ! grep -qE "^exit_code=[0-9]+$" "$GITHUB_OUTPUT"; then
  echo "FAIL: GITHUB_OUTPUT must contain exit_code=<numeric value>" >&2
  echo "(empty exit_code= means the upstream EXIT=\$? capture was lost)" >&2
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

# (f) The summary step must have appended the verdict to
# $GITHUB_STEP_SUMMARY. Without this, push-mode has no human-visible
# surface for the verdict — the artifact is download-only.
if [[ ! -s "$GITHUB_STEP_SUMMARY" ]]; then
  echo "FAIL: \$GITHUB_STEP_SUMMARY is empty after the summary step" >&2
  echo "(push-mode needs the verdict to surface on the run page; the artifact alone is invisible to a developer scrolling past CI)" >&2
  exit 2
fi
# Verify the appended content has the actual verdict body, not just
# the heading. The reporter's comment.md always contains the verdict
# emoji + a "Required checkpoints:" or zone-summary line.
if ! grep -qE "(Red-zone files changed|All changes in blue zones|boundary violation|Required checkpoints)" "$GITHUB_STEP_SUMMARY"; then
  echo "FAIL: \$GITHUB_STEP_SUMMARY content doesn't look like a reporter verdict" >&2
  echo "--- \$GITHUB_STEP_SUMMARY contents ---" >&2
  cat "$GITHUB_STEP_SUMMARY" >&2
  exit 2
fi

echo "ok: push-mode workflow run-block runs end-to-end"
echo "  - extracted reporter + summary run-blocks from scaffold.md"
echo "  - executed against a 2-commit fixture (BEFORE/AFTER diff)"
echo "  - reporter produced build/verdict.json with verdict=RED"
echo "  - GITHUB_OUTPUT got exit_code=$CAPTURED_EXIT (the enforce step's input)"
echo "  - run-block exited 0 (canonical: subsequent steps run; enforce gates on exit_code)"
echo "  - \$GITHUB_STEP_SUMMARY received the verdict ($(wc -c < "$GITHUB_STEP_SUMMARY") bytes; this is what surfaces on the run page)"
