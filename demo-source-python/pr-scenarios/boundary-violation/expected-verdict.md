# Expected verdict

```
## agent-redline: BOUNDARY_VIOLATION

**1 boundary violation(s) detected.**

| Zone | Files |
|---|---|
| Watch | `src/orders/domain/order.py` |

**Boundary violations:**
- `Domain stays free of infrastructure` (error): orders.domain is not allowed to import orders.infrastructure (e.g. orders.domain.order -> orders.infrastructure.db.in_memory_orders)

**API check:** no changes
**PR size:** 1 files / ~3 lines (ok)
```

- Verdict: BOUNDARY_VIOLATION
- Exit code: 2 (binding for `boundary_violation` per the policy)
- CI: red (the `boundary` job's import-linter call exits 1; the `report` job runs and surfaces the violation; the policy's `modes.perCheck.boundary_violation: binding` makes the reporter exit non-zero)
- The PR cannot merge until the structure is fixed
