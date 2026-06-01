#!/usr/bin/env bash
# Mutates a clean main checkout to produce the boundary-violation-pr
# diff: orders/domain/order.py imports from orders/infrastructure/.
set -euo pipefail

DOMAIN="src/orders/domain/order.py"
[[ -f "$DOMAIN" ]] || { echo "error: $DOMAIN not found" >&2; exit 1; }

python3 <<'PYEOF'
from pathlib import Path
p = Path("src/orders/domain/order.py")
text = p.read_text(encoding="utf-8")
forbidden_import = "from orders.infrastructure.db.in_memory_orders import InMemoryOrdersRepository"
marker = "# boundary-violation marker"
if forbidden_import not in text:
    text = text.replace(
        "from dataclasses import dataclass",
        "from dataclasses import dataclass\n" + forbidden_import,
    )
if marker not in text:
    text = text.replace(
        "@dataclass(frozen=True)",
        marker + "\n_illegal_ref = InMemoryOrdersRepository  # noqa: violates layered architecture\n\n\n@dataclass(frozen=True)",
    )
p.write_text(text, encoding="utf-8")
print("modified domain/order.py")
PYEOF
