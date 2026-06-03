#!/usr/bin/env bash
# tests/scaffold-ci-e2e/check-spring-ci-e2e.sh
#
# End-to-end check: extract the openapi-from-controllers reporter
# run-block from extensions/jvm-archunit/scaffold.md (§6), execute
# it against a Spring-shaped fixture with hand-crafted spec files, and
# assert the reporter produces the expected verdict.
#
# This catches the same class of bug as Python's e2e test, for the
# Spring path: the structural test confirms the run-block has the
# right pattern elements; this confirms it ACTUALLY WORKS — env vars
# line up, --api-spec-base/--api-spec-head flags accept the inputs,
# the reporter call's flag set is valid, the verdict shape is right.
#
# We don't run Gradle. The scaffold's run-block expects two spec files
# at /tmp/spec_base.yaml and /tmp/spec_head.yaml — in real CI those
# come from `./gradlew generateOpenApiDocs` at base+head SHAs. Here we
# substitute them with hand-crafted fixtures that exercise the
# api-changed signal: base spec has /orders, head spec adds /orders/{id}.
#
# Strategy:
#   1. Extract the reporter run-block from spring scaffold §6.
#   2. Build a minimal Spring-shaped fixture: agent-policy.yaml +
#      vendored reporter + 2 commits (so BASE/HEAD diff works).
#   3. Substitute github-context expressions with our shell vars.
#   4. Substitute /tmp/spec_*.yaml paths with our fixture paths.
#   5. Execute. Assert verdict.json exists with verdict reflecting the
#      api change, GITHUB_OUTPUT captures the exit code, run-block
#      itself exits 0 (canonical pattern).
#
# Exit codes:
#   0 — Spring reporter run-block executes end-to-end correctly
#   1 — script error
#   2 — workflow run-block produced wrong output

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCAFFOLD="$REPO_ROOT/extensions/jvm-archunit/scaffold.md"
REPORTER="$REPO_ROOT/core/reporter/reporter.py"
EXTRACTOR="$(dirname "${BASH_SOURCE[0]}")/_extract-spring.py"

[[ -f "$SCAFFOLD" ]] || { echo "error: Spring scaffold not found" >&2; exit 1; }
[[ -f "$REPORTER" ]] || { echo "error: reporter not found" >&2; exit 1; }
[[ -f "$EXTRACTOR" ]] || { echo "error: extractor not found at $EXTRACTOR" >&2; exit 1; }
command -v python >/dev/null || { echo "error: python not on PATH" >&2; exit 1; }
command -v git >/dev/null || { echo "error: git not on PATH" >&2; exit 1; }
# Note: the scaffold's run-block uses jq to extract PR labels from
# GITHUB_EVENT_PATH, but we substitute that line away below (we don't
# have a real Actions event payload), so jq isn't a runtime requirement
# for this test.

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# ----------------------------------------------------------------------
# Step 1: Extract the reporter run-block.
# ----------------------------------------------------------------------

if ! python "$EXTRACTOR" "$SCAFFOLD" > "$TMPDIR/extracted.sh" 2> "$TMPDIR/extract.err"; then
  echo "FAIL: Spring extractor failed:" >&2
  cat "$TMPDIR/extract.err" >&2
  exit 2
fi

if [[ ! -s "$TMPDIR/extracted.sh" ]]; then
  echo "FAIL: extractor produced empty output" >&2
  exit 2
fi

echo "==> step 1: extracted Spring reporter run-block from scaffold.md §6"

# ----------------------------------------------------------------------
# Step 2: Build the Spring-shaped fixture.
# ----------------------------------------------------------------------

FIXTURE="$TMPDIR/fixture"
mkdir -p "$FIXTURE/scripts"
cd "$FIXTURE"
git init -q -b main
git config user.email "t@t"
git config user.name "t"

# Vendored reporter (what bootstrap drops into a Spring repo).
cp "$REPORTER" "$FIXTURE/scripts/agent-redline-report.py"

# Spring-shaped policy: red on controller path; declares
# api: openapi-from-controllers (since that's what §6 is for).
cat > agent-policy.yaml <<'POLICY_EOF'
version: 1
project:
  name: spring-e2e-fixture
  extension: jvm-archunit
zones:
  red:
    - path: "src/main/java/**/controller/**"
      reason: API entry point
      checkpoint: api-review
  blue:
    - path: "src/test/**"
      reason: tests
api:
  type: openapi-from-controllers
  generationCommand: ./gradlew generateOpenApiDocs
  diffMode: structural
  checkpoint: api-review
checkpoints:
  api-review:
    satisfiedBy:
      - codeownerApproval
      - label: api-reviewed
modes:
  default: shadow
POLICY_EOF

# Two commits — BEFORE has the controller, HEAD modifies it.
mkdir -p src/main/java/com/example/controller
cat > src/main/java/com/example/controller/OrderController.java <<'JAVA_EOF'
package com.example.controller;

public class OrderController {
    public String list() { return "orders"; }
}
JAVA_EOF

git add . agent-policy.yaml scripts/agent-redline-report.py
git commit -q -m "init"
BEFORE_SHA=$(git rev-parse HEAD)

# Modify the controller to simulate an API touch
cat > src/main/java/com/example/controller/OrderController.java <<'JAVA_EOF'
package com.example.controller;

public class OrderController {
    public String list() { return "orders"; }
    public String getById(Long id) { return "order " + id; }   // new endpoint
}
JAVA_EOF

git add .
git commit -q -m "add getById to OrderController"
AFTER_SHA=$(git rev-parse HEAD)

echo "==> step 2: Spring fixture built (BEFORE=${BEFORE_SHA:0:8} AFTER=${AFTER_SHA:0:8})"

# ----------------------------------------------------------------------
# Step 3: Hand-crafted OpenAPI spec files (what `./gradlew
# generateOpenApiDocs` would have produced at base+head). The diff
# shows /orders/{id} is added — exercises the api-spec-diff path.
# ----------------------------------------------------------------------

mkdir -p "$TMPDIR/specs"
cat > "$TMPDIR/specs/spec_base.yaml" <<'SPEC_EOF'
openapi: 3.0.0
info:
  title: Orders
  version: "1.0"
paths:
  /orders:
    get:
      summary: List orders
      responses:
        "200":
          description: ok
SPEC_EOF

cat > "$TMPDIR/specs/spec_head.yaml" <<'SPEC_EOF'
openapi: 3.0.0
info:
  title: Orders
  version: "1.0"
paths:
  /orders:
    get:
      summary: List orders
      responses:
        "200":
          description: ok
  /orders/{id}:
    get:
      summary: Get one order
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: integer
      responses:
        "200":
          description: ok
SPEC_EOF

echo "==> step 3: hand-crafted base+head OpenAPI specs (head adds /orders/{id})"

# ----------------------------------------------------------------------
# Step 4: Substitute github-context expressions AND the /tmp/spec_*
# paths (the scaffold hardcodes those — bypass for the test).
# ----------------------------------------------------------------------

sed -i \
  -e 's|${{ github.event.pull_request.base.sha }}|$GH_BEFORE|g' \
  -e 's|${{ github.event.pull_request.head.sha }}|$GH_AFTER|g' \
  -e "s|/tmp/spec_base\.yaml|$TMPDIR/specs/spec_base.yaml|g" \
  -e "s|/tmp/spec_head\.yaml|$TMPDIR/specs/spec_head.yaml|g" \
  "$TMPDIR/extracted.sh"

# Skip the jq labels query — it requires GITHUB_EVENT_PATH which we don't have.
# Replace the entire `--pr-labels "..."` line with empty labels.
sed -i \
  -e 's|--pr-labels "$(jq[^"]*"[^"]*"[^"]*)"|--pr-labels ""|' \
  "$TMPDIR/extracted.sh"

# Sanity: no more $(...) evaluations left that would touch live env
if grep -q 'jq -r' "$TMPDIR/extracted.sh"; then
  # The substitution above is fragile — fall back to deleting any line
  # that still calls jq, since we can't satisfy the GITHUB_EVENT_PATH
  # requirement here.
  sed -i '/jq -r/d' "$TMPDIR/extracted.sh"
fi

export GITHUB_OUTPUT="$TMPDIR/github_output"
: > "$GITHUB_OUTPUT"
export GH_BEFORE="$BEFORE_SHA"
export GH_AFTER="$AFTER_SHA"

echo "==> step 4: substitutions applied (github-context + spec paths)"

# ----------------------------------------------------------------------
# Step 5: Execute and assert.
# ----------------------------------------------------------------------

cd "$FIXTURE"
set +e
bash "$TMPDIR/extracted.sh" > "$TMPDIR/run.log" 2>&1
RC=$?
set -e

echo "==> step 5: run-block executed (exit $RC)"

# (a) verdict.json must exist
if [[ ! -f "$FIXTURE/build/verdict.json" ]]; then
  echo "FAIL: reporter did not produce build/verdict.json" >&2
  echo "--- run output ---" >&2
  cat "$TMPDIR/run.log" >&2
  exit 2
fi

# (b) verdict reflects an API change (red-zone change to controller +
# api-spec diff). The verdict should be RED, API_CHANGE, or MIXED.
python - "$FIXTURE/build/verdict.json" <<'ASSERT_EOF'
import json, sys
v = json.load(open(sys.argv[1]))
verdict = v.get("verdict")
acceptable = {"RED", "API_CHANGE", "MIXED"}
if verdict not in acceptable:
    print(f"FAIL: verdict is {verdict!r}, expected one of {acceptable}", file=sys.stderr)
    sys.exit(2)

# Also assert: api-spec diff produced a non-empty diff (the head spec
# adds /orders/{id}, so the reporter MUST detect it).
api = v.get("apiChanges", {})
if not api.get("detected"):
    print(f"FAIL: apiChanges.detected is False; expected True given the spec diff", file=sys.stderr)
    print(f"verdict.json apiChanges: {api}", file=sys.stderr)
    sys.exit(2)

# Tighter assertion: the structural-diff signal must specifically show
# pathsAdded=['/orders/{id}']. This pins the openapi-from-controllers
# path. Drop --api-spec-head and the reporter falls back to "head is
# empty -> all base paths look removed" — pathsAdded would be empty.
spec_diff = api.get("specDiff", {})
paths_added = spec_diff.get("pathsAdded", [])
if "/orders/{id}" not in paths_added:
    print(
        f"FAIL: apiChanges.specDiff.pathsAdded does not contain '/orders/{{id}}'; "
        f"the head spec adds this path so the reporter must detect it. "
        f"Got pathsAdded={paths_added}, full apiChanges={api}",
        file=sys.stderr,
    )
    sys.exit(2)

print(f"  verdict={verdict}; apiChanges.detected={api.get('detected')}; pathsAdded={paths_added}")
ASSERT_EOF

# (c) GITHUB_OUTPUT must capture exit_code WITH a numeric value (not empty).
# `exit_code=` alone (no value) means the upstream `EXIT=$?` capture was
# dropped — the enforce step would see an empty string and behave wrongly.
if ! grep -qE "^exit_code=[0-9]+$" "$GITHUB_OUTPUT"; then
  echo "FAIL: GITHUB_OUTPUT must contain exit_code=<numeric value>" >&2
  echo "(empty exit_code= means the upstream EXIT=\$? capture was lost)" >&2
  cat "$GITHUB_OUTPUT" >&2
  exit 2
fi

# (d) Run-block itself MUST exit 0 (canonical pattern: subsequent steps
# need to run; enforce step is what propagates non-zero on exit_code 2).
if [[ "$RC" -ne 0 ]]; then
  echo "FAIL: run-block exited $RC; canonical pattern requires 0 so subsequent steps run" >&2
  cat "$TMPDIR/run.log" >&2
  exit 2
fi

CAPTURED_EXIT=$(grep "^exit_code=" "$GITHUB_OUTPUT" | tail -1 | cut -d= -f2)
echo "ok: Spring reporter run-block runs end-to-end"
echo "  - extracted run-block from jvm-archunit/scaffold.md §6"
echo "  - executed against a 2-commit Spring fixture (controller modified)"
echo "  - reporter consumed --api-spec-base / --api-spec-head + diffed them"
echo "  - reporter produced build/verdict.json with apiChanges.detected=true"
echo "  - GITHUB_OUTPUT got exit_code=$CAPTURED_EXIT"
echo "  - run-block exited 0 (canonical: subsequent steps run)"
