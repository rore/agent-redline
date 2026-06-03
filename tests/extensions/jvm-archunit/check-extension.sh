#!/usr/bin/env bash
# tests/extensions/jvm-archunit/check-extension.sh
#
# Layer 3 dry-run for the jvm-archunit extension.
#
# Verifies that:
#   1. The example fixture (examples/spring-hexagonal/) builds and the
#      ArchUnit tests pass on a clean tree.
#   2. Injecting a known boundary violation makes the right rule fail.
#   3. Restoring the fixture brings the tests back to passing.
#
# Requires: Java 21+ and Gradle (or the system has gradle installed).
#
# Exit codes:
#   0 — both passes worked as expected
#   1 — script error (missing dependency, fixture, etc.)
#   2 — unexpected outcome (clean tree failed; injected violation didn't fail; etc.)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
FIXTURE="$REPO_ROOT/examples/spring-hexagonal"
ARCH_TEST="$FIXTURE/src/test/java/com/example/orders/architecture/DependencyArchitectureTest.java"
SERVICE="$FIXTURE/src/main/java/com/example/orders/application/OrderService.java"
SERVICE_BACKUP="$(mktemp)"
trap 'cp "$SERVICE_BACKUP" "$SERVICE" 2>/dev/null || true; rm -f "$SERVICE_BACKUP"' EXIT

# Sanity checks
[[ -d "$FIXTURE" ]] || { echo "error: fixture not found at $FIXTURE" >&2; exit 1; }
[[ -f "$ARCH_TEST" ]] || { echo "error: architecture test not found at $ARCH_TEST" >&2; exit 1; }
[[ -f "$SERVICE" ]] || { echo "error: service not found at $SERVICE" >&2; exit 1; }
command -v gradle >/dev/null 2>&1 || { echo "error: gradle not on PATH" >&2; exit 1; }

cd "$FIXTURE"

# Step 1 — clean tree should pass the architecture tests
echo "==> step 1: clean architecture test"
if ! gradle --no-daemon test --tests '*ArchitectureTest' >/tmp/agent-redline-step1.log 2>&1; then
  echo "FAIL: architecture tests failed on a clean fixture" >&2
  tail -50 /tmp/agent-redline-step1.log >&2
  exit 2
fi
echo "ok: architecture tests pass on clean fixture"

# Step 2 — inject a known violation and verify the rule fires
echo "==> step 2: inject violation; expect failure"
cp "$SERVICE" "$SERVICE_BACKUP"
# Add a forbidden import: application/OrderService importing the persistence adapter.
python3 - <<'PYEOF'
import sys
from pathlib import Path
service = Path("src/main/java/com/example/orders/application/OrderService.java")
text = service.read_text(encoding="utf-8")
# Add the forbidden import below the existing imports (idempotent).
forbidden = "import com.example.orders.adapter.persistence.PostgresOrderRepository;"
if forbidden not in text:
    text = text.replace(
        "import com.example.orders.domain.Order;",
        "import com.example.orders.domain.Order;\n" + forbidden,
    )
# Use the imported class to ensure ArchUnit detects the dependency,
# not just the import statement.
marker = "// boundary-violation marker"
if marker not in text:
    text = text.replace(
        "public class OrderService {",
        "public class OrderService {\n    " + marker + "\n    "
        "private final Class<?> _illegalRef = PostgresOrderRepository.class;\n"
    )
service.write_text(text, encoding="utf-8")
print("violation injected")
PYEOF

if gradle --no-daemon test --tests '*ArchitectureTest' >/tmp/agent-redline-step2.log 2>&1; then
  echo "FAIL: architecture tests passed after injecting a violation" >&2
  exit 2
fi

# Verify the right rule failed (application_must_not_depend_on_persistence_adapters)
if ! grep -q "application_must_not_depend_on_persistence_adapters" /tmp/agent-redline-step2.log; then
  echo "FAIL: a rule failed but not the one we expected" >&2
  echo "(expected: application_must_not_depend_on_persistence_adapters)" >&2
  tail -30 /tmp/agent-redline-step2.log >&2
  exit 2
fi
echo "ok: injected violation triggered the right rule"

# Step 3 — restore (handled by EXIT trap) and re-verify clean state
echo "==> step 3: restore and re-verify"
cp "$SERVICE_BACKUP" "$SERVICE"
if ! gradle --no-daemon test --tests '*ArchitectureTest' >/tmp/agent-redline-step3.log 2>&1; then
  echo "FAIL: architecture tests failed after restore" >&2
  exit 2
fi
echo "ok: architecture tests pass after restore"

echo
echo "all 3 step(s) passed."
