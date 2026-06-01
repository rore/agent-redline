#!/usr/bin/env bash
# tests/run-all.sh
#
# Top-level local test runner for agent-redline.
#
# Runs every test layer in order. Designed to be runnable on a developer
# laptop with sub-10-second total time (excluding optional Java steps).
# CI runs the same script in a clean environment.
#
# Usage:
#   ./tests/run-all.sh                    # run everything
#   ./tests/run-all.sh --skip extension   # skip a layer
#   ./tests/run-all.sh --only reporter    # run just one layer
#   ./tests/run-all.sh --verbose          # show per-test detail
#
# Exit codes:
#   0  — all enabled layers pass
#   N  — first failing layer's index (1..N)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SKIP=()
ONLY=""
VERBOSE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip) SKIP+=("$2"); shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --verbose|-v) VERBOSE=1; shift ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

# ----------------------------------------------------------------------
# Each layer: (name, command, optional-marker).
# Optional layers (marked OPTIONAL) print a clear note when their
# prerequisites are missing rather than failing.
# ----------------------------------------------------------------------

layers=(
  "budget|bash tests/budget/check-budget.sh|"
  "schema|python tests/schema/check-schema.py|REQUIRES_PYTHON"
  "reporter-goldens|python tests/reporter/check-reporter.py|REQUIRES_PYTHON"
  "reporter-unit|python -m pytest tests/reporter/ -q|REQUIRES_PYTEST"
  "workflow-scripts|bash tests/workflow-scripts/test-diff-inputs.sh|"
  "links|python tests/links/check-links.py|REQUIRES_PYTHON"
  "gitignore|bash tests/gitignore/check-gitignore.sh|"
  "package|bash tests/package/check-package.sh|REQUIRES_PYTHON"
  "sync-demo|bash tests/sync/test-sync-demo.sh|"
  "extension-spring|bash tests/extensions/spring-archunit/check-extension.sh|OPTIONAL_GRADLE"
  "extension-python|bash tests/extensions/python/check-extension.sh|OPTIONAL_IMPORTLINTER"
)

# ----------------------------------------------------------------------
# Prereq detection
# ----------------------------------------------------------------------

has_python() { command -v python >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1; }
has_pytest() { python -m pytest --version >/dev/null 2>&1; }
has_gradle() { command -v gradle >/dev/null 2>&1; }
has_importlinter() { python -c "import importlinter" >/dev/null 2>&1; }

prereq_ok() {
  case "$1" in
    "") return 0 ;;
    REQUIRES_PYTHON) has_python ;;
    REQUIRES_PYTEST) has_pytest ;;
    OPTIONAL_GRADLE) has_gradle ;;
    OPTIONAL_IMPORTLINTER) has_importlinter ;;
    *) return 0 ;;
  esac
}

prereq_msg() {
  case "$1" in
    REQUIRES_PYTHON) echo "python not on PATH" ;;
    REQUIRES_PYTEST) echo "pytest not installed (pip install pytest)" ;;
    OPTIONAL_GRADLE) echo "gradle not on PATH (Java toolchain required); skipping" ;;
    OPTIONAL_IMPORTLINTER) echo "import-linter not installed (pip install 'import-linter>=2.0,<3'); skipping" ;;
    *) echo "missing prerequisite: $1" ;;
  esac
}

is_optional() {
  case "$1" in
    OPTIONAL_*) return 0 ;;
    *) return 1 ;;
  esac
}

# ----------------------------------------------------------------------
# Run
# ----------------------------------------------------------------------

failed_layer=""
failed_index=0
index=0
ran=0
skipped=0

for entry in "${layers[@]}"; do
  index=$(( index + 1 ))
  IFS='|' read -r name cmd marker <<< "$entry"

  if [[ -n "$ONLY" && "$ONLY" != "$name" ]]; then
    continue
  fi

  for s in "${SKIP[@]:-}"; do
    if [[ "$s" == "$name" ]]; then
      printf "==> skip   %-22s (--skip)\n" "$name"
      skipped=$(( skipped + 1 ))
      continue 2
    fi
  done

  if ! prereq_ok "$marker"; then
    if is_optional "$marker"; then
      printf "==> skip   %-22s ($(prereq_msg "$marker"))\n" "$name"
      skipped=$(( skipped + 1 ))
      continue
    else
      printf "==> FAIL   %-22s ($(prereq_msg "$marker"))\n" "$name"
      failed_layer="$name"
      failed_index=$index
      break
    fi
  fi

  start=$(date +%s)
  if (( VERBOSE )); then
    printf "==> run    %-22s :: %s\n" "$name" "$cmd"
    if ! eval "$cmd"; then
      end=$(date +%s)
      printf "==> FAIL   %-22s (%ds)\n" "$name" $(( end - start ))
      failed_layer="$name"
      failed_index=$index
      break
    fi
    end=$(date +%s)
    printf "==> ok     %-22s (%ds)\n" "$name" $(( end - start ))
  else
    if ! out=$(eval "$cmd" 2>&1); then
      end=$(date +%s)
      echo "$out"
      printf "==> FAIL   %-22s (%ds)\n" "$name" $(( end - start ))
      failed_layer="$name"
      failed_index=$index
      break
    fi
    end=$(date +%s)
    printf "==> ok     %-22s (%ds)\n" "$name" $(( end - start ))
  fi
  ran=$(( ran + 1 ))
done

echo
if [[ -n "$failed_layer" ]]; then
  echo "FAILED at layer $failed_index ($failed_layer). Ran $ran, skipped $skipped."
  exit "$failed_index"
fi
echo "all $ran layer(s) passed; $skipped skipped."
