#!/usr/bin/env bash
# tests/extensions/python/check-extension.sh
#
# Layer 3 dry-run for the python extension.
#
# Verifies that:
#   1. The example fixture (examples/python-fastapi/) passes import-linter
#      contracts on a clean tree, the adapter script writes a valid
#      json-violations report (empty), and exit code is 0.
#   2. Injecting a known boundary violation (domain importing infrastructure)
#      causes the adapter script to emit a violation in the JSON report,
#      and exit code is 1.
#   3. The reporter, fed the boundary-violation JSON, produces a
#      BOUNDARY_VIOLATION verdict.
#   4. Restoring the fixture brings the tree back to clean.
#
# Requires: Python 3.10+ with import-linter, pyyaml, and jsonschema installed.
#
# Exit codes:
#   0 — all steps passed
#   1 — script error (missing dependency, fixture, etc.)
#   2 — unexpected outcome

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
FIXTURE="$REPO_ROOT/examples/python-fastapi"
ADAPTER="$REPO_ROOT/extensions/python/scripts/run-import-linter.py"
DEMO_POLICY="$REPO_ROOT/demo-source-python/agent-policy.yaml"
REPORTER="$REPO_ROOT/core/reporter/reporter.py"
SCHEMA="$REPO_ROOT/core/schema/boundary-violations.schema.json"

ORDER_FILE="$FIXTURE/src/orders/domain/order.py"
ORDER_BACKUP="$(mktemp)"
TMPDIR_LOCAL="$(mktemp -d)"
trap 'cp "$ORDER_BACKUP" "$ORDER_FILE" 2>/dev/null || true; rm -f "$ORDER_BACKUP"; rm -rf "$TMPDIR_LOCAL"' EXIT

[[ -d "$FIXTURE" ]] || { echo "error: fixture not found at $FIXTURE" >&2; exit 1; }
[[ -f "$ADAPTER" ]] || { echo "error: adapter not found at $ADAPTER" >&2; exit 1; }
[[ -f "$DEMO_POLICY" ]] || { echo "error: demo policy not found at $DEMO_POLICY" >&2; exit 1; }
[[ -f "$REPORTER" ]] || { echo "error: reporter not found at $REPORTER" >&2; exit 1; }
[[ -f "$ORDER_FILE" ]] || { echo "error: order.py not found at $ORDER_FILE" >&2; exit 1; }
command -v python >/dev/null 2>&1 || { echo "error: python not on PATH" >&2; exit 1; }

if ! python -c "import importlinter" 2>/dev/null; then
  echo "error: import-linter not installed (pip install 'import-linter>=2.0,<3')" >&2
  exit 1
fi

cp "$ORDER_FILE" "$ORDER_BACKUP"
cd "$FIXTURE"
mkdir -p build

# Step 1 — clean fixture: adapter exit 0, JSON valid, no violations.
echo "==> step 1: clean fixture; expect no violations"
if ! python "$ADAPTER" --out build/import-linter-report.json > "$TMPDIR_LOCAL/step1.log" 2>&1; then
  echo "FAIL: adapter exited non-zero on a clean fixture" >&2
  cat "$TMPDIR_LOCAL/step1.log" >&2
  exit 2
fi
SCHEMA_PATH="$SCHEMA" python - <<'PYEOF'
import json, os, sys
from pathlib import Path
from jsonschema import Draft202012Validator
schema = json.loads(Path(os.environ["SCHEMA_PATH"]).read_text(encoding="utf-8"))
report = json.loads(Path("build/import-linter-report.json").read_text(encoding="utf-8"))
errs = list(Draft202012Validator(schema).iter_errors(report))
if errs:
    print("schema errors:", [e.message for e in errs], file=sys.stderr)
    sys.exit(2)
if report.get("violations"):
    print(f"unexpected violations on clean tree: {report['violations']}", file=sys.stderr)
    sys.exit(2)
print("ok: clean tree passes contracts; report is empty and valid")
PYEOF

# Step 2 — inject a violation; expect adapter exit 1 and a violation in JSON.
echo "==> step 2: inject violation; expect adapter to detect"
python - <<'PYEOF'
from pathlib import Path
p = Path("src/orders/domain/order.py")
text = p.read_text(encoding="utf-8")
forbidden = "from orders.infrastructure.db.in_memory_orders import InMemoryOrdersRepository"
marker = "# boundary-violation marker (test injection)"
if forbidden not in text:
    text = text.replace(
        "from dataclasses import dataclass",
        "from dataclasses import dataclass\n" + forbidden,
    )
if marker not in text:
    text = text.replace(
        "@dataclass(frozen=True)",
        marker + "\n_illegal = InMemoryOrdersRepository  # noqa\n\n\n@dataclass(frozen=True)",
    )
p.write_text(text, encoding="utf-8")
print("injected violation")
PYEOF

set +e
python "$ADAPTER" --out build/import-linter-report.json > "$TMPDIR_LOCAL/step2.log" 2>&1
adapter_exit=$?
set -e
if [[ "$adapter_exit" -ne 1 ]]; then
  echo "FAIL: adapter exit code is $adapter_exit (expected 1) after injecting a violation" >&2
  cat "$TMPDIR_LOCAL/step2.log" >&2
  exit 2
fi

SCHEMA_PATH="$SCHEMA" python - <<'PYEOF'
import json, os, sys
from pathlib import Path
from jsonschema import Draft202012Validator
schema = json.loads(Path(os.environ["SCHEMA_PATH"]).read_text(encoding="utf-8"))
report = json.loads(Path("build/import-linter-report.json").read_text(encoding="utf-8"))
errs = list(Draft202012Validator(schema).iter_errors(report))
if errs:
    print("schema errors:", [e.message for e in errs], file=sys.stderr)
    sys.exit(2)
violations = report.get("violations", [])
if not violations:
    print("FAIL: expected violations after injection; got 0", file=sys.stderr)
    sys.exit(2)
matches = [v for v in violations
           if "infrastructure" in v.get("rule", "").lower()
              or "infrastructure" in v.get("detail", "")]
if not matches:
    print(f"FAIL: no violation mentions infrastructure: {violations}", file=sys.stderr)
    sys.exit(2)
print(f"ok: adapter reported {len(violations)} violation(s); right rule fired")
PYEOF

# Step 3 — reporter sees the JSON, produces BOUNDARY_VIOLATION.
echo "==> step 3: reporter -> BOUNDARY_VIOLATION verdict"
echo "src/orders/domain/order.py" > "$TMPDIR_LOCAL/changed-files.txt"
python "$REPORTER" \
  --policy "$DEMO_POLICY" \
  --changed-files "$TMPDIR_LOCAL/changed-files.txt" \
  --boundary-report build/import-linter-report.json \
  --boundary-format json-violations \
  --json-out "$TMPDIR_LOCAL/verdict.json" \
  > /dev/null 2>&1 || true

VERDICT_FILE="$TMPDIR_LOCAL/verdict.json" python - <<'PYEOF'
import json, os, sys
from pathlib import Path
v = json.loads(Path(os.environ["VERDICT_FILE"]).read_text(encoding="utf-8"))
if v.get("verdict") != "BOUNDARY_VIOLATION":
    print(f"FAIL: verdict is {v.get('verdict')!r}, expected BOUNDARY_VIOLATION", file=sys.stderr)
    sys.exit(2)
if v.get("exitCode") != 2:
    print(f"FAIL: exitCode is {v.get('exitCode')}, expected 2", file=sys.stderr)
    sys.exit(2)
sources = {bv.get("source") for bv in v.get("boundaryViolations", [])}
if "import-linter" not in sources:
    print(f"FAIL: boundaryViolations[].source is {sources}, expected to include 'import-linter'", file=sys.stderr)
    sys.exit(2)
print("ok: reporter verdict is BOUNDARY_VIOLATION (exitCode 2, source import-linter)")
PYEOF

# Step 4 — restore and verify clean state.
echo "==> step 4: restore and re-verify clean"
cp "$ORDER_BACKUP" "$ORDER_FILE"
if ! python "$ADAPTER" --out build/import-linter-report.json > "$TMPDIR_LOCAL/step4.log" 2>&1; then
  echo "FAIL: adapter exited non-zero after restore" >&2
  cat "$TMPDIR_LOCAL/step4.log" >&2
  exit 2
fi
python - <<'PYEOF'
import json, sys
from pathlib import Path
report = json.loads(Path("build/import-linter-report.json").read_text(encoding="utf-8"))
if report.get("violations"):
    print(f"FAIL: tree not clean after restore: {report['violations']}", file=sys.stderr)
    sys.exit(2)
print("ok: tree clean after restore")
PYEOF

# Step 5 — multi-package layout fixture: each layer is its own top-level
# package at repo root (no parent), import-linter uses root_packages
# (plural). The fixture has a baked-in violation (api -> storage); we
# don't inject — we just assert the adapter detects the existing one.
echo "==> step 5: multi-package layout fixture; adapter must detect existing violation"
MULTIPKG_FIXTURE="$REPO_ROOT/extensions/python/scripts/_test_fixture_multipkg"
[[ -d "$MULTIPKG_FIXTURE" ]] || { echo "error: multipkg fixture not found at $MULTIPKG_FIXTURE" >&2; exit 1; }

cd "$MULTIPKG_FIXTURE"
mkdir -p build
set +e
python "$ADAPTER" --out build/import-linter-report.json > "$TMPDIR_LOCAL/step5.log" 2>&1
multipkg_exit=$?
set -e
if [[ "$multipkg_exit" -ne 1 ]]; then
  echo "FAIL: multipkg adapter exit code is $multipkg_exit (expected 1)" >&2
  cat "$TMPDIR_LOCAL/step5.log" >&2
  exit 2
fi

SCHEMA_PATH="$SCHEMA" python - <<'PYEOF'
import json, os, sys
from pathlib import Path
from jsonschema import Draft202012Validator
schema = json.loads(Path(os.environ["SCHEMA_PATH"]).read_text(encoding="utf-8"))
report = json.loads(Path("build/import-linter-report.json").read_text(encoding="utf-8"))
errs = list(Draft202012Validator(schema).iter_errors(report))
if errs:
    print("schema errors:", [e.message for e in errs], file=sys.stderr)
    sys.exit(2)
violations = report.get("violations", [])
if not violations:
    print("FAIL: multipkg fixture should have violations", file=sys.stderr)
    sys.exit(2)
# Detail must reference top-level package names (api, storage), proving the
# multi-package metadata flows correctly through the adapter.
detail = violations[0].get("detail", "")
if "api" not in detail or "storage" not in detail:
    print(f"FAIL: detail doesn't reference top-level packages api/storage: {detail!r}", file=sys.stderr)
    sys.exit(2)
print(f"ok: multipkg adapter detected violation with top-level package names ({detail!r})")
PYEOF

echo
echo "all 5 step(s) passed."
