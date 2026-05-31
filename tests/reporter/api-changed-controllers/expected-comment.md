## agent-redline: API_CHANGE

**Public API contract changed.**

| Zone | Files |
|---|---|
| Red | `src/main/java/com/example/orders/ui/controller/OrderController.java`, `src/main/java/com/example/orders/ui/controller/RefundController.java` |
| Blue | `src/test/java/com/example/orders/ui/controller/OrderControllerTest.java` |

**Required checkpoints:**
- [ ] `api-review` — red-zone change: src/main/java/com/example/orders/ui/controller/OrderController.java. Satisfy by: label `api-reviewed`

**Boundary check:** passed
**API check:** structural changes detected

Removed:
- `/refunds`

Modified:
- `/orders` (+DELETE ~GET)

**PR size:** 3 files / 0 lines (ok)
