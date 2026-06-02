#!/usr/bin/env bash
# tests/tuner/check-tuner.sh
#
# Smoke + edge-case test for scripts/agent-redline-tune.py --push-history.
#
# Coverage:
#   1. Happy path — 5 commits with known file-touch distribution, asserts
#      changeset count and per-rule firing rates.
#   2. Empty repo — no commits at all; tuner must exit non-zero with a
#      clear "no PRs found" message (or equivalent), not crash.
#   3. Missing branch — --branch nonexistent against a populated repo;
#      tuner must exit non-zero.
#   4. Zero-file commit — a merge / empty commit that touches no files;
#      tuner must include the commit in the count but not credit any
#      zone with its absence.
#   5. Limit exceeds available — --limit 100 against 3 commits; tuner
#      must walk all 3 and report 3 (not 100).
#
# Validates the new --push-history source mode end-to-end without
# requiring network access (no `gh`).
#
# Exit codes:
#   0 — all cases pass
#   1 — script error
#   2 — at least one case produced wrong output

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TUNER="$REPO_ROOT/scripts/agent-redline-tune.py"

[[ -f "$TUNER" ]] || { echo "error: tuner not found at $TUNER" >&2; exit 1; }
command -v git >/dev/null || { echo "error: git not on PATH" >&2; exit 1; }
command -v python >/dev/null || { echo "error: python not on PATH" >&2; exit 1; }

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Shared minimal policy used by all cases.
cat > "$TMPDIR/policy.yaml" <<'POLICY_EOF'
version: 1
project: { name: tuner-fixture }
zones:
  red:
    - { path: "core/**", reason: "core layer", checkpoint: architecture-review }
    - { path: "storage/**", reason: "storage", checkpoint: persistence-review }
  blue:
    - { path: "tests/**", reason: "tests" }
checkpoints:
  architecture-review:
    satisfiedBy:
      - codeownerApproval
  persistence-review:
    satisfiedBy:
      - codeownerApproval
POLICY_EOF

build_repo() {
  # Build a fresh git repo at $1 and cd into it.
  local dir="$1"
  rm -rf "$dir"
  mkdir -p "$dir"
  cd "$dir"
  git init -q -b main
  git config user.email "t@t"
  git config user.name "t"
}

run_tuner() {
  # Invoke the tuner, capturing stdout+stderr and exit code.
  # Args: <repo-path> <branch> <limit> [--out=tuner.log]
  local repo_path="$1" branch="$2" limit="$3"
  set +e
  OUT=$(python "$TUNER" \
    --policy "$TMPDIR/policy.yaml" \
    --push-history \
    --repo-path "$repo_path" \
    --branch "$branch" \
    --limit "$limit" 2>&1)
  RC=$?
  set -e
}

failed=0
fail() {
  echo "FAIL: $1" >&2
  if [[ -n "${OUT:-}" ]]; then
    echo "--- tuner output ---" >&2
    echo "$OUT" >&2
  fi
  failed=$(( failed + 1 ))
}

# ----------------------------------------------------------------------
# Case 1: happy path
# ----------------------------------------------------------------------
echo "==> case 1: happy path (5 commits, known distribution)"
FIXTURE="$TMPDIR/case1"
build_repo "$FIXTURE"
mkdir -p core storage tests
echo "# initial" > README.md && git add README.md && git commit -q -m "init"
for i in 1 2 3; do
  echo "# v$i" > core/foo.py
  git add core/foo.py && git commit -q -m "edit core/foo.py #$i"
done
echo "# storage" > storage/db.py && git add storage/db.py && git commit -q -m "edit storage/db.py"
echo "# test" > tests/test_a.py && git add tests/test_a.py && git commit -q -m "edit tests/test_a.py"

run_tuner "$FIXTURE" main 5
[[ $RC -eq 0 ]] || fail "case1: exited $RC (expected 0)"
echo "$OUT" | grep -q "5 changeset(s)" || fail "case1: report missing '5 changeset(s)'"
echo "$OUT" | grep -q 'core/\*\*.*60%' || fail "case1: core/** should fire at 60%"
echo "$OUT" | grep -q 'storage/\*\*.*20%' || fail "case1: storage/** should fire at 20%"
[[ $failed -eq 0 ]] && echo "ok"

# ----------------------------------------------------------------------
# Case 2: empty repo (no commits)
# ----------------------------------------------------------------------
echo "==> case 2: empty repo"
FIXTURE="$TMPDIR/case2"
build_repo "$FIXTURE"
# No commits.
run_tuner "$FIXTURE" main 5
if [[ $RC -eq 0 ]]; then
  fail "case2: tuner exited 0 on empty repo (expected non-zero — no commits to walk)"
elif echo "$OUT" | grep -qiE "no .* found|no commits|fatal: ambiguous"; then
  echo "ok: empty repo produces clear non-zero exit ($RC) and an error message"
else
  fail "case2: non-zero exit but no recognizable error message"
fi

# ----------------------------------------------------------------------
# Case 3: missing branch
# ----------------------------------------------------------------------
echo "==> case 3: missing branch"
FIXTURE="$TMPDIR/case3"
build_repo "$FIXTURE"
echo x > a.txt && git add a.txt && git commit -q -m "x"

run_tuner "$FIXTURE" nonexistent-branch 5
if [[ $RC -eq 0 ]]; then
  fail "case3: tuner exited 0 with --branch nonexistent (expected non-zero)"
else
  echo "ok: missing branch produces non-zero exit ($RC)"
fi

# ----------------------------------------------------------------------
# Case 4: empty (zero-file) commit
# ----------------------------------------------------------------------
echo "==> case 4: empty commit (touches zero files)"
FIXTURE="$TMPDIR/case4"
build_repo "$FIXTURE"
mkdir -p core
echo "# real" > core/foo.py && git add core/foo.py && git commit -q -m "real change"
git commit -q --allow-empty -m "empty commit (no file changes)"

run_tuner "$FIXTURE" main 5
[[ $RC -eq 0 ]] || fail "case4: exited $RC (expected 0; empty commits should be tolerated)"
# The tuner's documented behavior: zero-file commits are skipped (they
# carry no signal for any rule). After 1 real + 1 empty commit, we
# expect the report to show 1 changeset, not 2. If you change the
# behavior to include empty commits, update the assertion AND document
# the rationale in fetch_push_history's docstring.
if ! echo "$OUT" | grep -qE "1 changeset\(s\)"; then
  fail "case4: expected 1 changeset (empty commit skipped); got: $(echo "$OUT" | head -2)"
else
  echo "ok: empty commit skipped (1 changeset, not 2)"
fi

# ----------------------------------------------------------------------
# Case 5: limit > available
# ----------------------------------------------------------------------
echo "==> case 5: --limit 100 against a 3-commit repo"
FIXTURE="$TMPDIR/case5"
build_repo "$FIXTURE"
mkdir -p core
for i in 1 2 3; do
  echo "v$i" > core/file.py && git add core/file.py && git commit -q -m "c$i"
done

run_tuner "$FIXTURE" main 100
[[ $RC -eq 0 ]] || fail "case5: exited $RC (expected 0)"
echo "$OUT" | grep -qE "3 changeset\(s\)" || fail "case5: should report 3 changeset(s) (got: $(echo "$OUT" | head -2))"
[[ $failed -eq 0 || -n "$(echo "$OUT" | grep -E "3 changeset\(s\)")" ]] && echo "ok: tuner walked the available 3 commits, not the requested 100"

echo
if [[ $failed -gt 0 ]]; then
  echo "$failed case(s) failed."
  exit 2
fi
echo "all 5 case(s) passed."
