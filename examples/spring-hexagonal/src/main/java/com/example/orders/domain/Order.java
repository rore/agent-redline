package com.example.orders.domain;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * Order aggregate root.
 *
 * Domain invariants live here. Treat as red zone: changes to the model
 * invariants require architecture-review.
 */
public final class Order {

    public enum Status { PLACED, SHIPPED, CANCELLED }

    private final UUID id;
    private final BigDecimal total;
    private final Instant placedAt;
    private Status status;

    public Order(UUID id, BigDecimal total, Instant placedAt) {
        if (id == null) throw new IllegalArgumentException("id required");
        if (total == null || total.signum() < 0) throw new IllegalArgumentException("total must be non-negative");
        if (placedAt == null) throw new IllegalArgumentException("placedAt required");
        this.id = id;
        this.total = total;
        this.placedAt = placedAt;
        this.status = Status.PLACED;
    }

    public UUID id() { return id; }
    public BigDecimal total() { return total; }
    public Instant placedAt() { return placedAt; }
    public Status status() { return status; }

    public void ship() {
        if (status != Status.PLACED) {
            throw new IllegalStateException("only placed orders can ship");
        }
        status = Status.SHIPPED;
    }
}
