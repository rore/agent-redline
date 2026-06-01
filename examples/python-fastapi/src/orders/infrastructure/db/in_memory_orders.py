"""In-memory implementation of OrdersRepository — minimal adapter for the demo."""

from __future__ import annotations

from orders.domain.order import Order
from orders.domain.repositories.orders_repository import OrdersRepository


class InMemoryOrdersRepository(OrdersRepository):
    def __init__(self) -> None:
        self._store: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._store[order.id] = order

    def get(self, order_id: str) -> Order | None:
        return self._store.get(order_id)
