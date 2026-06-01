"""Place-order use case. Application orchestrates domain + ports."""

from __future__ import annotations
from uuid import uuid4

from orders.domain.order import Order
from orders.domain.repositories.orders_repository import OrdersRepository


def place_order(
    customer_id: str,
    item_sku: str,
    quantity: int,
    repository: OrdersRepository,
) -> Order:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    order = Order(
        id=uuid4().hex,
        customer_id=customer_id,
        item_sku=item_sku,
        quantity=quantity,
    )
    repository.save(order)
    return order
