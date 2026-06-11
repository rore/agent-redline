## agent-redline: BOUNDARY_VIOLATION

**1 boundary violation(s) detected.**

| Zone | Files |
|---|---|
| Gray | `src/main/java/com/example/orders/api/OrderController.java` |

**Required checkpoints:**
- [ ] `architecture-review` — Suppression marker on guarded surface: @SuppressWarnings at src/main/java/com/example/orders/api/OrderController.java:11. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary violations:**
- `domain_must_not_import_adapters` (error): Architecture Violation: Rule 'no classes that reside in a package '..domain..' should depend on classes that reside in any package ['..adapter..']' was violated (1 times): Class <com.example.orders.domain.Order> depends on <com.example.orders.adapter.persistence.OrderRow>


**Suppressions added (1):**

| File | Line | Marker | Zone |
|---|---|---|---|
| `src/main/java/com/example/orders/api/OrderController.java` | 11 | `@SuppressWarnings` | gray |

Suppressions on guarded surfaces require `architecture-review`.

[Why this matters](docs/agent/boundary-violation.md#suppressions)

**API check:** no changes
**PR size:** 1 files / 2 lines (ok)
