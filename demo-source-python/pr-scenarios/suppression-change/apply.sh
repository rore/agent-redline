#!/usr/bin/env bash
# pr-scenarios/suppression-change/apply.sh
#
# Mutates a clean main checkout to produce the suppression-change-pr diff:
# adds `# noqa: import-linter` on the OrdersRepository port import line
# to demonstrate the suppression-detection feature on a red-zone file.

set -euo pipefail

PORT="src/orders/domain/repositories/orders_repository.py"
[[ -f "$PORT" ]] || { echo "error: $PORT not found" >&2; exit 1; }

python3 <<'PYEOF'
from pathlib import Path
p = Path("src/orders/domain/repositories/orders_repository.py")
text = p.read_text(encoding="utf-8")
if "# noqa" not in text:
    text = text.replace(
        "from orders.domain.order import Order\n",
        "from orders.domain.order import Order  # noqa: import-linter\n",
    )
    p.write_text(text, encoding="utf-8")
    print("modified orders_repository.py")
else:
    print("already modified")
PYEOF
