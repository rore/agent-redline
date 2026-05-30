# Expected verdict (verified live on agent-redline-demo PR #11)

When the `architecture-reviewed` label is applied:

```
## agent-redline: RED

**Red-zone files changed.**

| Zone | Files |
|---|---|
| Red | `src/main/java/com/example/orders/domain/Order.java` |

**Required checkpoints:**
- [x] `architecture-review` — red-zone change: src/main/java/com/example/orders/domain/Order.java. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary check:** passed
**API check:** no changes
**PR size:** 1 files / 7 lines (ok)
```

- Verdict: RED
- Exit code: 0 (checkpoint satisfied)
- CI: green (archunit job passes; report job posts comment with the checkpoint marked satisfied)

If the label is removed, the checkpoint flips to `[ ]` (unsatisfied) and the report's exit code becomes 1 (warn) under shadow mode.
