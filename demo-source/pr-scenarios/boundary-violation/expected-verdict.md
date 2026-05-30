# Expected verdict

```
agent-redline: BOUNDARY_VIOLATION
1 boundary violation(s) detected.

Boundary violations:
- application_must_not_depend_on_persistence_adapters (error):
  Class <com.example.orders.application.OrderService> depends on
  <com.example.orders.adapter.persistence.PostgresOrderRepository>
```

Exit code 2. ArchUnit job fails (binding). CI red. PR cannot merge.
