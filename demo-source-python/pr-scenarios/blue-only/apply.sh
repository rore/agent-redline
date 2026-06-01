#!/usr/bin/env bash
# Mutates a clean main checkout to produce the blue-only-pr diff:
# adds a single isolated test file in tests/.
set -euo pipefail

cat > tests/test_isolated_helper.py <<'EOF'
"""A pure helper test that doesn't touch production code."""

from orders.domain.order import Order


def test_order_total_units_returns_quantity():
    o = Order(id="abc", customer_id="c-1", item_sku="sku-A", quantity=3)
    assert o.total_units() == 3


def test_order_is_frozen():
    o = Order(id="abc", customer_id="c-1", item_sku="sku-A", quantity=1)
    import dataclasses
    assert dataclasses.is_dataclass(o)
    # Frozen dataclasses raise on attribute set.
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        o.quantity = 99  # type: ignore[misc]
EOF
echo "added tests/test_isolated_helper.py"
