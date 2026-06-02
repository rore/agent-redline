# Expected verdict (push-mode)

The run summary at the top of github.com/{owner}/{repo}/actions/runs/{id} shows:

```
## agent-redline verdict

## agent-redline: BOUNDARY_VIOLATION

**1 boundary violation(s) detected.**

| Zone | Files |
|---|---|
| Watch | `src/orders/domain/order.py` |

**Boundary violations:**
- `Domain stays free of infrastructure` (error): orders.domain is not allowed to import orders.infrastructure (e.g. orders.domain.order -> orders.infrastructure.db.in_memory_orders)

**API check:** no changes
**Change size:** 1 files / ~3 lines (ok)
```

- Verdict: BOUNDARY_VIOLATION
- Reporter exit code: 2 (binding-mode hard fail per `modes.perCheck.boundary_violation: binding`)
- Workflow conclusion: **failure** — agent-redline workflow itself is red. Other workflows in the repo run independently.
- GitHub's default email-on-failure notification fires.
- Run-summary visible on the run page; the offending import chain is named precisely.
- The red badge persists on this commit's agent-redline run as the historical record. The architectural rule was violated; the structure should be fixed (or the violation explicitly baselined via `ignore_imports` in `pyproject.toml`, which is itself a red-zone change).
