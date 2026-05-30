#!/usr/bin/env bash
# pr-scenarios/blue-only/apply.sh
#
# Mutates a clean main checkout to produce the blue-only-pr diff:
# add a customerNotes field to OrderRow.

set -euo pipefail

ORDER_ROW="src/main/java/com/example/orders/adapter/persistence/dto/OrderRow.java"
[[ -f "$ORDER_ROW" ]] || { echo "error: $ORDER_ROW not found" >&2; exit 1; }

python3 <<'PYEOF'
from pathlib import Path
p = Path("src/main/java/com/example/orders/adapter/persistence/dto/OrderRow.java")
text = p.read_text(encoding="utf-8")
if "customerNotes" not in text:
    text = text.replace(
        "    Instant placedAt,\n    String status",
        "    Instant placedAt,\n    String status,\n    String customerNotes",
    )
    p.write_text(text, encoding="utf-8")
    print("modified OrderRow.java")
else:
    print("already modified")
PYEOF
