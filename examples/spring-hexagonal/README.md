# spring-hexagonal — Layer 3 fixture

A minimal Spring Boot service in hexagonal layout. Used inside the agent-redline repo as the **Layer 3 extension scaffold dry-run target** (see `tests/extensions/spring-archunit/check-extension.sh` and `docs/VALIDATION.md`).

This is **not** a runnable demo of the agent-redline framework. It has no `agent-policy.yaml`, no `AGENTS.md`, no CI workflow, no per-checkpoint docs. For the live demo with all those artifacts and three planned PRs, see the paired repo: `agent-redline-demo`.

## Why minimal

The Layer 3 dry-run only needs three things to verify the boundary-rule backend works:

1. A Spring service with a recognizable hexagonal layout (`domain`, `application/port`, `adapter/persistence`, `controller`).
2. An ArchUnit test class that encodes a few boundary rules.
3. A buildable `build.gradle` so `gradle test --tests '*ArchitectureTest'` can run.

Adding a policy here would muddy the role: the dry-run harness doesn't need one, and a policy at this path would not be picked up as the repo-root policy by an agent (the example sits inside agent-redline, so its repo root is agent-redline's, not this directory's).

## Layout

```
src/main/java/com/example/orders/
├── domain/                      ← red zone in the demo repo
│   └── Order.java
├── application/
│   ├── port/                    ← red zone (port interfaces)
│   │   └── OrderRepository.java
│   └── OrderService.java        ← gray-watch (orchestration)
├── adapter/persistence/         ← blue zone (impl)
│   ├── PostgresOrderRepository.java
│   └── dto/
│       └── OrderRow.java
└── controller/                  ← red zone (API surface)
    └── OrderController.java

src/test/java/com/example/orders/
├── architecture/                ← red zone (boundary-rule definitions)
│   └── DependencyArchitectureTest.java
└── OrderServiceTest.java        ← blue zone

src/main/resources/db/migration/
└── V1__create_orders.sql        ← red zone (persistence contract)
```

## Running locally

```bash
gradle test                                    # full test run
gradle test --tests '*ArchitectureTest'        # boundary rules only
```

The Layer 3 harness (`tests/extensions/spring-archunit/check-extension.sh` in the agent-redline repo) runs both, then injects a deliberate boundary violation, verifies the right rule fails, and restores the fixture.

## See also

- `agent-redline-demo` repo — the runnable, paired demo repo with policy, CI, and three planned PRs
- `extensions/spring-archunit/` in agent-redline — the language extension this fixture is shaped for
- `docs/VALIDATION.md` Layer 3 in agent-redline — the dry-run validation strategy
