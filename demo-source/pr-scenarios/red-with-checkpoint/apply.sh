#!/usr/bin/env bash
# pr-scenarios/red-with-checkpoint/apply.sh
#
# Mutates a clean main checkout to produce the red-with-checkpoint-pr
# diff: add a cancel() method to the Order aggregate.

set -euo pipefail

ORDER="src/main/java/com/example/orders/domain/Order.java"
[[ -f "$ORDER" ]] || { echo "error: $ORDER not found" >&2; exit 1; }

python3 <<'PYEOF'
from pathlib import Path
p = Path("src/main/java/com/example/orders/domain/Order.java")
text = p.read_text(encoding="utf-8")
if "public void cancel()" not in text:
    text = text.replace(
        "    public void ship() {",
        """    public void cancel() {
        if (status == Status.SHIPPED) {
            throw new IllegalStateException("cannot cancel a shipped order");
        }
        status = Status.CANCELLED;
    }

    public void ship() {""",
    )
    p.write_text(text, encoding="utf-8")
    print("modified Order.java")
else:
    print("already modified")
PYEOF
