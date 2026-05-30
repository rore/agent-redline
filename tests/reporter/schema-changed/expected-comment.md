## agent-redline: SCHEMA_CHANGE

**Persistence schema changed.**

| Zone | Files |
|---|---|
| Blue | `src/test/java/com/example/orders/OrderServiceTest.java` |
| Gray | `src/main/resources/db/migration/V2__add_orders_index.sql` |

**Required checkpoints:**
- [ ] `persistence-review` — Persistence migration changed. Satisfy by: label `persistence-reviewed`

**Boundary check:** passed
**API check:** no changes
**Schema check:** changes detected
**PR size:** 2 files / 0 lines (ok)
