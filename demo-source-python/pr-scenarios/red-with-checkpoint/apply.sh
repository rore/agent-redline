#!/usr/bin/env bash
# Mutates a clean main checkout to produce the red-with-checkpoint-pr diff:
# adds a count() method to OrdersRepository and its in-memory adapter.
set -euo pipefail

PORT="src/orders/domain/repositories/orders_repository.py"
ADAPTER="src/orders/infrastructure/db/in_memory_orders.py"
[[ -f "$PORT" ]] || { echo "error: $PORT not found" >&2; exit 1; }
[[ -f "$ADAPTER" ]] || { echo "error: $ADAPTER not found" >&2; exit 1; }

python3 <<'PYEOF'
from pathlib import Path

# Add count() to the port.
port = Path("src/orders/domain/repositories/orders_repository.py")
text = port.read_text(encoding="utf-8")
if "def count" not in text:
    text = text.rstrip() + """

    def count(self) -> int:
        \"\"\"How many orders are stored. New port method — every adapter must implement.\"\"\"
        ...
"""
    port.write_text(text, encoding="utf-8")

# Implement count() in the in-memory adapter.
adapter = Path("src/orders/infrastructure/db/in_memory_orders.py")
text = adapter.read_text(encoding="utf-8")
if "def count" not in text:
    text = text.rstrip() + """

    def count(self) -> int:
        return len(self._store)
"""
    adapter.write_text(text, encoding="utf-8")

print("added count() to port + adapter")
PYEOF
