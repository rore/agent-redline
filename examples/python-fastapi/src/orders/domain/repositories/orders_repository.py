"""OrdersRepository port — the domain's contract with persistence.

This file is in agent-redline's red zone (architecture-review). Adding,
removing, or changing a method here is a structural decision affecting
every adapter that implements it.
"""

from __future__ import annotations
from typing import Protocol

from orders.domain.order import Order


class OrdersRepository(Protocol):
    """Port: how the application asks for / saves orders."""

    def save(self, order: Order) -> None:
        ...

    def get(self, order_id: str) -> Order | None:
        ...
