#!/usr/bin/env bash
# tests/skill-scripts-runnable/check-skill-scripts-runnable.sh
#
# Invokes every Python script that ships in the packaged skill with
# --help (or equivalent introspection), from outside the source repo,
# and asserts none of them raise import errors. Catches the class of
# bug Pallium hit twice now: a script ships in dist/ that imports a
# module that doesn't ship.
#
# Round 2 (skill-refs) catches DANGLING PATH REFERENCES in markdown
# (e.g. `scripts/agent-redline-report.sh` referenced from a scaffold
# but never written). It does NOT catch DANGLING IMPORT REFERENCES
# (e.g. tune.py: `from core.reporter import ...` when core/ doesn't
# ship). This test fills that gap.
#
# Strategy:
#   1. cd to a clean tempdir (so we can't accidentally pick up the
#      upstream repo's `core/` package via cwd-on-sys.path).
#   2. For each *.py in dist/agent-redline/scripts/: invoke it with
#      --help, capture exit + stderr. Asserts:
#        - exit code 0 (the most common Python --help convention)
#        - stderr does NOT contain ModuleNotFoundError or ImportError
#   3. Same for extension-shipped scripts in dist/agent-redline/
#      extensions/*/scripts/.
#   4. Files starting with `_` are private (importable helpers, not
#      CLIs). Skip them.
#
# Exit codes:
#   0 — every shipped CLI script invokes cleanly with --help
#   1 — script error (dist not built, python missing)
#   2 — at least one shipped script raised an import error or
#       --help failed

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST="$REPO_ROOT/dist/agent-redline"

[[ -d "$DIST" ]] || { echo "error: dist not built at $DIST" >&2; exit 1; }
command -v python >/dev/null || { echo "error: python not on PATH" >&2; exit 1; }

# Run from a clean tempdir so the upstream repo's `core/` (which IS
# importable when cwd is the repo root) cannot mask the bug.
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

cd "$WORK"

failures=0
checked=0
skipped=0

# Find every CLI script in the packaged skill. Skip files prefixed `_`
# (private importable helpers, not invokable CLIs).
mapfile -t scripts < <(find "$DIST" -path '*/scripts/*.py' -type f | sort)

for script in "${scripts[@]}"; do
  base=$(basename "$script")
  if [[ "$base" == _* ]]; then
    skipped=$(( skipped + 1 ))
    continue
  fi
  checked=$(( checked + 1 ))

  set +e
  out=$(python "$script" --help 2>&1)
  rc=$?
  set -e

  rel="${script#"$DIST/"}"
  if [[ $rc -ne 0 ]]; then
    echo "FAIL  $rel: --help exited $rc" >&2
    echo "$out" | head -5 | sed 's/^/    /' >&2
    failures=$(( failures + 1 ))
    continue
  fi
  if echo "$out" | grep -qE "ModuleNotFoundError|ImportError"; then
    echo "FAIL  $rel: import error during --help" >&2
    echo "$out" | grep -E "ModuleNotFoundError|ImportError|^Traceback" | head -3 | sed 's/^/    /' >&2
    failures=$(( failures + 1 ))
    continue
  fi
  echo "ok    $rel"
done

echo
if (( failures > 0 )); then
  echo "$failures of $checked shipped script(s) had import / invocation errors." >&2
  exit 2
fi
echo "all $checked shipped script(s) invoke cleanly with --help; $skipped private helper(s) skipped."
