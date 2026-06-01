## agent-redline: BOUNDARY_VIOLATION

**1 boundary violation(s) detected.**

| Zone | Files |
|---|---|
| Red | `src/orders/domain/order.py` |

**Required checkpoints:**
- [ ] `architecture-review` — red-zone change: src/orders/domain/order.py. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary violations:**
- `Layered architecture` (error): src.orders.domain.order -> src.orders.infrastructure.db.session (forbidden by 'layers' contract)

**API check:** no changes
**PR size:** 1 files / 0 lines (ok)
