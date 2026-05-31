# Expected verdict (verified live on agent-redline-demo PR #12)

```
## agent-redline: BOUNDARY_VIOLATION

**1 boundary violation(s) detected.**

| Zone | Files |
|---|---|
| Gray | `src/main/java/com/example/orders/application/OrderService.java` |
| Watch | `src/main/java/com/example/orders/application/OrderService.java` |

**Boundary violations:**
- `application_must_not_depend_on_persistence_adapters` (error): Architecture Violation: Rule '...' was violated (1 times): Class <com.example.orders.application.OrderService> depends on <com.example.orders.adapter.persistence.PostgresOrderRepository>

**API check:** no changes
**PR size:** 1 files / 4 lines (ok)
```

- Verdict: BOUNDARY_VIOLATION
- Exit code: 2 (binding for `boundary_violation` per the policy)
- CI: red (the `archunit` job fails outright; the `report` job runs after with `if: always()` and surfaces the violation in the PR comment)
- The PR cannot merge until the structure is fixed
