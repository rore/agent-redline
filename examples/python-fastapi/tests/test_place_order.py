"""Smoke test: place an order via the place_order use case."""

from orders.application.place_order import place_order
from orders.infrastructure.db.in_memory_orders import InMemoryOrdersRepository


def test_place_order_persists_through_repository():
    repo = InMemoryOrdersRepository()
    order = place_order(
        customer_id="c-1",
        item_sku="sku-A",
        quantity=2,
        repository=repo,
    )
    assert repo.get(order.id) is not None
    assert order.quantity == 2


def test_place_order_rejects_zero_quantity():
    repo = InMemoryOrdersRepository()
    import pytest
    with pytest.raises(ValueError):
        place_order(customer_id="c-1", item_sku="sku-A", quantity=0, repository=repo)
