package com.example.orders.adapter.persistence.dto;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * Database row representation. Internal to the persistence adapter.
 *
 * Treat as blue zone: this is purely an internal mapping type and does
 * NOT appear in any external API surface.
 */
public record OrderRow(
    UUID id,
    BigDecimal total,
    Instant placedAt,
    String status
) {}
