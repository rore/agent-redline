package com.example.orders.adapter.persistence;

import com.example.orders.adapter.persistence.dto.OrderRow;
import com.example.orders.application.port.OrderRepository;
import com.example.orders.domain.Order;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Postgres-backed adapter. Implements the OrderRepository port.
 *
 * Implementation detail of persistence; the application layer must NOT
 * import this class directly — only the port.
 *
 * For the fixture, this is an in-memory stub. In a real service it would
 * use JPA / JdbcTemplate / etc.
 */
public class PostgresOrderRepository implements OrderRepository {

    private final Map<UUID, OrderRow> store = new HashMap<>();

    @Override
    public Optional<Order> findById(UUID id) {
        OrderRow row = store.get(id);
        if (row == null) return Optional.empty();
        Order order = new Order(row.id(), row.total(), row.placedAt());
        if ("SHIPPED".equals(row.status())) order.ship();
        return Optional.of(order);
    }

    @Override
    public void save(Order order) {
        store.put(order.id(), new OrderRow(
            order.id(),
            order.total(),
            order.placedAt(),
            order.status().name()
        ));
    }

    // Test helper; in real code this would be a database fixture.
    public void seed(UUID id, BigDecimal total, Instant placedAt) {
        store.put(id, new OrderRow(id, total, placedAt, "PLACED"));
    }
}
