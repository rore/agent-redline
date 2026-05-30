## agent-redline: RED

**Red-zone files changed.**

| Zone | Files |
|---|---|
| Red | `src/main/java/com/example/orders/domain/Order.java` |
| Blue | `src/test/java/com/example/orders/OrderServiceTest.java` |
| Gray | `src/main/java/com/example/orders/util/DateNormalizer.java` |

**Required checkpoints:**
- [ ] `architecture-review` — red-zone change: src/main/java/com/example/orders/domain/Order.java. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary check:** passed
**API check:** no changes
**PR size:** 3 files / 0 lines (ok)
