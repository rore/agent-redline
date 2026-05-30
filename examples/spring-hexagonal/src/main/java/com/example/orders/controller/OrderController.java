package com.example.orders.controller;

import com.example.orders.application.OrderService;

import java.util.UUID;

/**
 * REST controller — public API surface.
 *
 * Treat as red zone: changes here change what consumers can call. The
 * spring-archunit profile generates OpenAPI from controller annotations,
 * so any change to method signatures or return types is an API change.
 *
 * For the fixture, this is a plain class without Spring annotations; in
 * a real service it would carry @RestController, @RequestMapping, etc.
 */
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    /** POST /orders/{id}/ship */
    public void shipOrder(UUID id) {
        orderService.shipOrder(id);
    }
}
