# Expected verdict (target state for the demo)

When the `api-reviewed` label is applied:

```
## agent-redline: API_CHANGE

**Public API contract changed.**

| Zone | Files |
|---|---|
| Red   | `src/main/java/com/example/orders/controller/OrderController.java` |
| Watch | `src/main/java/com/example/orders/application/OrderService.java` |

**Required checkpoints:**
- [x] `api-review` — red-zone change: src/main/java/com/example/orders/controller/OrderController.java. Satisfy by: CODEOWNER approval or label `api-reviewed`

**Boundary check:** passed
**API check:** structural changes detected

Added:
- `POST /orders/{id}/cancel`

**PR size:** 2 files / ~15 lines (ok)
```

- Verdict: `API_CHANGE`
- Exit code: 0 (checkpoint satisfied via the label)
- CI: `archunit` green, `generate-specs` green, `report` green

If the label is removed, the checkpoint flips to `[ ]` (unsatisfied) and
the report's exit code becomes 1 (warn) under shadow mode. Under binding
mode the PR would be merge-blocked.

The structural diff section under "API check" is the value-add of
`api.type: openapi-from-controllers`: it tells the reviewer *what changed
on the contract*, not just *that something changed*. Without the spec
diff the reporter would still emit `api-review` (path-based) but the
comment would only say "API check: changes detected" with no shape.
