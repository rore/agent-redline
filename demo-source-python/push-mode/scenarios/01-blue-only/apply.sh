#!/usr/bin/env bash
# Apply the push-demo blue-only scenario: add an isolated test.
# Same diff as pr-scenarios/blue-only — different surfacing path.
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
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        o.quantity = 99  # type: ignore[misc]
EOF
echo "added tests/test_isolated_helper.py"
