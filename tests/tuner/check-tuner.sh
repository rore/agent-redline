#!/usr/bin/env bash
# tests/tuner/check-tuner.sh
#
# Smoke test for scripts/agent-redline-tune.py --push-history mode.
# Builds a tiny throwaway git repo with 5 commits, each touching a
# specific file. Runs the tuner against a policy that classifies those
# files as red. Asserts:
#   1. tuner exits 0
#   2. report says "5 changeset(s)"
#   3. each red rule's firing rate matches the actual touch count
#
# This validates the new --push-history source mode end-to-end without
# requiring network access (no `gh`) or a real Pallium-shaped repo.
#
# Exit codes:
#   0 — tuner output matches expected
#   1 — script error
#   2 — tuner output diverged from expected

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TUNER="$REPO_ROOT/scripts/agent-redline-tune.py"

[[ -f "$TUNER" ]] || { echo "error: tuner not found at $TUNER" >&2; exit 1; }
command -v git >/dev/null || { echo "error: git not on PATH" >&2; exit 1; }
command -v python >/dev/null || { echo "error: python not on PATH" >&2; exit 1; }

# Disposable fixture
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
FIXTURE="$TMPDIR/repo"
mkdir -p "$FIXTURE"
cd "$FIXTURE"
git init -q -b main
git config user.email "t@t"
git config user.name "t"

# Build 5 commits, each touching ONE file we care about.
# - 3 commits touch core/foo.py (red, should fire 3/5 = 60%)
# - 1 commit touches storage/db.py (red, should fire 1/5 = 20%)
# - 1 commit touches tests/test_a.py (blue, should not fire on red)
mkdir -p core storage tests
echo "# initial" > README.md
git add README.md
git commit -q -m "init"

for i in 1 2 3; do
  echo "# v$i" > core/foo.py
  git add core/foo.py
  git commit -q -m "edit core/foo.py #$i"
done

echo "# storage" > storage/db.py
git add storage/db.py
git commit -q -m "edit storage/db.py"

echo "# test" > tests/test_a.py
git add tests/test_a.py
git commit -q -m "edit tests/test_a.py"

# Compose a minimal valid policy where core/** and storage/** are red,
# tests/** is blue. The tuner sees the 5 most recent commits (we built 5
# beyond the init).
cat > "$TMPDIR/policy.yaml" <<EOF
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
EOF

# Run the tuner with --push-history --limit 5 (5 most recent commits).
# Wrap in `set +e` so a non-zero exit from the tuner doesn't kill the
# test before we can inspect the output and assert against it.
set +e
OUT=$(python "$TUNER" \
  --policy "$TMPDIR/policy.yaml" \
  --push-history \
  --repo-path "$FIXTURE" \
  --branch main \
  --limit 5 2>&1)
RC=$?
set -e

if [[ $RC -ne 0 ]]; then
  echo "FAIL: tuner exited $RC (expected 0)" >&2
  echo "$OUT" >&2
  exit 2
fi

# Assert: report header says "5 changeset(s)"
if ! echo "$OUT" | grep -q "5 changeset(s)"; then
  echo "FAIL: report header missing '5 changeset(s)'" >&2
  echo "$OUT" >&2
  exit 2
fi

# Assert: core/** red rule fires on 3/5 (60%)
if ! echo "$OUT" | grep -q "core/\*\*.*60%"; then
  echo "FAIL: core/** rule should fire at 60% (3 of 5 commits); not found in:" >&2
  echo "$OUT" >&2
  exit 2
fi

# Assert: storage/** red rule fires on 1/5 (20%)
if ! echo "$OUT" | grep -q "storage/\*\*.*20%"; then
  echo "FAIL: storage/** rule should fire at 20% (1 of 5 commits); not found in:" >&2
  echo "$OUT" >&2
  exit 2
fi

echo "ok: tuner --push-history produced expected firing rates"
echo "  - 5 changesets sampled"
echo "  - core/**     -> 60% (3 of 5)"
echo "  - storage/**  -> 20% (1 of 5)"
