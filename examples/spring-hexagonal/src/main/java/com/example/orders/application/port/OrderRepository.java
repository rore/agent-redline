package com.example.orders.application.port;

import com.example.orders.domain.Order;

import java.util.Optional;
import java.util.UUID;

/**
 * Port the application uses to load/save orders.
 *
 * The interface is the architectural boundary. Adapters implement this;
 * application code depends only on this interface. Treat as red zone:
 * port shape changes require architecture-review.
 */
public interface OrderRepository {

    Optional<Order> findById(UUID id);

    void save(Order order);
}
