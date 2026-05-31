#!/usr/bin/env bash
# pr-scenarios/oversized/apply.sh
#
# Mutates a clean main checkout to add 60 trivial JUnit-shaped files
# under src/test/. All blue-zone, so the only signal that fires is the
# pr_size fail threshold (maxChangedFiles.fail: 50 in the demo policy).
#
# Output: 60 files in a fresh src/test/java/com/example/orders/oversized/
# directory, each with one no-op test method.

set -euo pipefail

DEST="src/test/java/com/example/orders/oversized"
mkdir -p "$DEST"

for i in $(seq -f "%02g" 1 60); do
    cat > "$DEST/Filler${i}Test.java" <<EOF
package com.example.orders.oversized;

import org.junit.jupiter.api.Test;

/**
 * Filler test #${i}. Exists only to inflate the PR file count past the
 * agent-policy.yaml fail threshold. Demonstrates the PR-size gate.
 */
class Filler${i}Test {
    @Test
    void noop_${i}() {
        // intentionally empty
    }
}
EOF
done

echo "added 60 filler test files under $DEST"
