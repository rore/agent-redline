#!/usr/bin/env bash
# tests/pre-push/check-pre-push.sh
#
# Targeted regressions for the pre-push-check.sh template. Catches the
# class of bug that bit Pallium's bootstrap: the awk pipeline computing
# LINES_CHANGED from `git diff --shortstat` produces empty output on
# empty diffs, and the reporter then rejects --lines-changed "" via
# argparse.
#
# What we test:
#   1. The awk pipeline emits "0" (not "") on empty input.
#   2. The script extracts a non-empty LINES_CHANGED for the empty-diff case.
#   3. The script syntax-checks (bash -n) cleanly.
#
# We don't run the FULL script end-to-end (that needs a vendored reporter,
# a policy, a base ref, etc.) — just the parts that broke.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$REPO_ROOT/core/templates/pre-push-check.sh"
DIST_SCRIPT="$REPO_ROOT/dist/agent-redline/assets/templates/pre-push-check.sh"

[[ -f "$SCRIPT" ]] || { echo "error: $SCRIPT not found" >&2; exit 1; }

# Step 1 — bash syntax check, both source and packaged.
echo "==> step 1: syntax check"
bash -n "$SCRIPT"
if [[ -f "$DIST_SCRIPT" ]]; then
  bash -n "$DIST_SCRIPT"
fi
echo "ok: bash -n passes"

# Step 2 — extract the awk pipeline from the source script and run it on
# empty input. The pipeline must emit "0", not "".
echo "==> step 2: awk pipeline on empty input"
# Find the awk command line. The script pipes shortstat output to awk on
# the line right after `git diff --shortstat`.
AWK_LINE=$(grep -A 1 "git diff --shortstat" "$SCRIPT" | grep "awk" | head -1)
if [[ -z "$AWK_LINE" ]]; then
  echo "FAIL: could not locate the awk pipeline in $SCRIPT" >&2
  exit 2
fi
# Strip leading pipe/whitespace and trailing close-paren/backslash so we
# can run just the awk part. Use BRE (no -E) so literal `|` doesn't get
# interpreted as alternation.
AWK_CMD=$(echo "$AWK_LINE" | sed 's/^[[:space:]]*|[[:space:]]*//; s/)[[:space:]]*$//; s/\\[[:space:]]*$//')
RESULT=$(printf "" | eval "$AWK_CMD")
if [[ "$RESULT" != "0" ]]; then
  echo "FAIL: awk pipeline output on empty input was '$RESULT', expected '0'" >&2
  echo "       awk cmd: $AWK_CMD" >&2
  exit 2
fi
echo "ok: awk pipeline emits '0' on empty input"

# Step 3 — confirm the script DEFAULTS LINES_CHANGED via :- fallback in case
# the awk pipeline ever regresses. Belt-and-suspenders.
echo "==> step 3: defensive :-0 fallback present"
if ! grep -q 'LINES_CHANGED=\${LINES_CHANGED:-0}' "$SCRIPT"; then
  echo "FAIL: $SCRIPT is missing the LINES_CHANGED=\${LINES_CHANGED:-0} fallback" >&2
  echo "       Without it, an awk regression would silently break the script." >&2
  exit 2
fi
echo "ok: defensive fallback present"

echo
echo "all 3 step(s) passed."
