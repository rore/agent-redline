"""HTTP entry point. The api layer wires FastAPI to the application."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from orders.application.place_order import place_order
from orders.infrastructure.db.in_memory_orders import InMemoryOrdersRepository


class PlaceOrderRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    item_sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)


class PlaceOrderResponse(BaseModel):
    order_id: str


def create_app() -> FastAPI:
    app = FastAPI(title="orders")
    repo = InMemoryOrdersRepository()

    @app.post("/orders", response_model=PlaceOrderResponse, status_code=201)
    def post_orders(payload: PlaceOrderRequest) -> PlaceOrderResponse:
        try:
            order = place_order(
                customer_id=payload.customer_id,
                item_sku=payload.item_sku,
                quantity=payload.quantity,
                repository=repo,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return PlaceOrderResponse(order_id=order.id)

    @app.get("/orders/{order_id}")
    def get_order(order_id: str) -> dict:
        order = repo.get(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="order not found")
        return {
            "id": order.id,
            "customer_id": order.customer_id,
            "item_sku": order.item_sku,
            "quantity": order.quantity,
        }

    return app


app = create_app()
