package com.example.orders;

import com.example.orders.adapter.persistence.PostgresOrderRepository;
import com.example.orders.application.OrderService;
import com.example.orders.application.port.OrderRepository;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

/**
 * Spring Boot bootstrap entry point.
 *
 * Exists so SpringDoc's OpenAPI generator has an application context to
 * start. Running `./gradlew generateOpenApiDocs` boots the app on a
 * random port, scrapes /v3/api-docs.yaml, writes the spec to
 * build/openapi.yaml, and shuts the app down.
 *
 * Important hexagonal note: the application and adapter classes
 * (`OrderService`, `PostgresOrderRepository`) deliberately do NOT carry
 * Spring annotations. They stay as pure POJOs. Wiring lives only here.
 * This keeps the inner layers framework-free; only the composition root
 * (this class) knows about Spring.
 *
 * For demo purposes only — the in-memory adapter doesn't need real
 * persistence, and the controller is the entire surface that matters.
 */
@SpringBootApplication
public class Application {

    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }

    @Bean
    OrderRepository orderRepository() {
        return new PostgresOrderRepository();
    }

    @Bean
    OrderService orderService(OrderRepository orderRepository) {
        return new OrderService(orderRepository);
    }
}
