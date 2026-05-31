package com.example.orders.controller;

import com.example.orders.application.OrderService;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

/**
 * REST controller — public API surface.
 *
 * Treat as red zone: changes here change what consumers can call. Because
 * this repo's `agent-policy.yaml` declares `api.type: openapi-from-controllers`,
 * the CI workflow generates an OpenAPI spec from these annotations at the
 * base and head SHAs of every PR; the agent-redline reporter diffs the two
 * specs and surfaces a structural API change in the PR comment.
 */
@RestController
@RequestMapping("/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @PostMapping("/{id}/ship")
    public ResponseEntity<Void> shipOrder(@PathVariable UUID id) {
        orderService.shipOrder(id);
        return ResponseEntity.noContent().build();
    }
}
