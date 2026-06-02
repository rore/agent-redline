#!/usr/bin/env bash
# scripts/agent-redline-check.sh
#
# Local pre-push check: runs pytest, import-linter (via the adapter),
# and the agent-redline reporter against the current diff vs. main.
#
# Mirrors what CI runs.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p build

echo "==> pytest"
python -m pytest -q

echo "==> import-linter (adapter -> json-violations)"
python scripts/run-import-linter.py --out build/import-linter-report.json || true

echo "==> agent-redline reporter"
git diff --name-only origin/main...HEAD > build/changed-files.txt
# Per-file line counts so policy.excludes applies to prSize.
git diff --numstat origin/main...HEAD > build/lines-per-file.txt
python scripts/agent-redline-report.py \
  --policy agent-policy.yaml \
  --changed-files build/changed-files.txt \
  --lines-per-file build/lines-per-file.txt \
  --boundary-report build/import-linter-report.json \
  --boundary-format json-violations \
  --json-out build/verdict.json \
  --comment-out build/comment.md

echo
echo "==> verdict"
cat build/comment.md
