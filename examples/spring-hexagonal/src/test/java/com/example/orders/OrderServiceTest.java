package com.example.orders;

import com.example.orders.adapter.persistence.PostgresOrderRepository;
import com.example.orders.application.OrderService;
import com.example.orders.domain.Order;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Regular unit test (blue zone). Lives outside the architecture/ package
 * so the architecture rules don't apply to it.
 */
class OrderServiceTest {

    @Test
    void shipping_a_placed_order_marks_it_shipped() {
        var repo = new PostgresOrderRepository();
        var orderId = UUID.randomUUID();
        repo.seed(orderId, BigDecimal.TEN, Instant.now());

        var service = new OrderService(repo);
        service.shipOrder(orderId);

        var loaded = repo.findById(orderId).orElseThrow();
        assertEquals(Order.Status.SHIPPED, loaded.status());
    }

    @Test
    void cannot_ship_unknown_order() {
        var repo = new PostgresOrderRepository();
        var service = new OrderService(repo);

        assertThrows(java.util.NoSuchElementException.class,
            () -> service.shipOrder(UUID.randomUUID()));
    }
}
