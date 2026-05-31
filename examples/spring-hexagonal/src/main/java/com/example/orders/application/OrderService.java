package com.example.orders.application;

import com.example.orders.application.port.OrderRepository;
import com.example.orders.domain.Order;

import java.util.NoSuchElementException;
import java.util.UUID;

/**
 * Application service. Orchestrates use cases over the domain.
 *
 * Depends on the port (OrderRepository), never on a concrete adapter.
 * Treat as watch: most feature work happens here; changes are common
 * but should be visible. The boundary rule "application must not import
 * concrete adapters" is the deterministic guard.
 */
public class OrderService {

    private final OrderRepository repository;

    public OrderService(OrderRepository repository) {
        this.repository = repository;
    }

    public void shipOrder(UUID orderId) {
        Order order = repository.findById(orderId)
            .orElseThrow(() -> new NoSuchElementException("order not found: " + orderId));
        order.ship();
        repository.save(order);
    }
}
