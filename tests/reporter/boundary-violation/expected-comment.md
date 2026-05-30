## agent-redline: BOUNDARY_VIOLATION

**1 boundary violation(s) detected.**

| Zone | Files |
|---|---|
| Gray | `src/main/java/com/example/orders/application/OrderService.java` |

**Boundary violations:**
- `application_must_not_depend_on_persistence_adapters` (error): Architecture Violation: Rule 'no classes that reside in a package '..application..' should depend on classes that reside in any package ['..adapter..persistence..']' was violated (1 times):

**API check:** no changes
**PR size:** 1 files / 0 lines (ok)
