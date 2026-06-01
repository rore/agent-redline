# Expected verdict

When the `architecture-reviewed` label is applied:

```
## agent-redline: RED

**Red-zone files changed.**

| Zone | Files |
|---|---|
| Red | `src/orders/domain/repositories/orders_repository.py` |
| Watch | `src/orders/infrastructure/db/in_memory_orders.py` |

**Required checkpoints:**
- [x] `architecture-review` — red-zone change: src/orders/domain/repositories/orders_repository.py. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary check:** passed
**API check:** no changes
**PR size:** 2 files / ~12 lines (ok)
```

- Verdict: RED
- Exit code: 1 (the watch-list file `in_memory_orders.py` triggers `review-warnings`; checkpoint itself is satisfied)
- CI: green (the boundary job passes; the report job posts the comment with the checkpoint marked satisfied)
- The PR is mergeable: the architecture-review checkpoint is the only gate the policy enforces, and it's satisfied via the label.

If the label is removed, the checkpoint flips to `[ ]` (unsatisfied) and CI behavior depends on the policy's `modes` configuration. The default `modes.default: shadow` keeps exit 1 (warn); flipping to `binding` would escalate to exit 2 (block).
