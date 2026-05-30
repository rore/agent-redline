#!/usr/bin/env bash
# pr-scenarios/boundary-violation/apply.sh
#
# Mutates a clean main checkout to produce the boundary-violation-pr
# diff: OrderService imports PostgresOrderRepository directly,
# bypassing the OrderRepository port.

set -euo pipefail

SERVICE="src/main/java/com/example/orders/application/OrderService.java"
[[ -f "$SERVICE" ]] || { echo "error: $SERVICE not found" >&2; exit 1; }

python3 <<'PYEOF'
from pathlib import Path
p = Path("src/main/java/com/example/orders/application/OrderService.java")
text = p.read_text(encoding="utf-8")
forbidden = "import com.example.orders.adapter.persistence.PostgresOrderRepository;"
marker = "// boundary-violation marker"
if forbidden not in text:
    text = text.replace(
        "import com.example.orders.domain.Order;",
        "import com.example.orders.domain.Order;\n" + forbidden,
    )
if marker not in text:
    text = text.replace(
        "public class OrderService {",
        "public class OrderService {\n    " + marker + "\n    "
        "private final Class<?> _illegalRef = PostgresOrderRepository.class;\n",
    )
p.write_text(text, encoding="utf-8")
print("modified OrderService.java")
PYEOF
