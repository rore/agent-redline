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
**PR size:** 1 files / ~3 lines (ok)
```

- Verdict: BOUNDARY_VIOLATION
- Reporter exit code: 2 (binding-mode hard fail per `modes.perCheck.boundary_violation: binding`)
- Workflow job: **red** (push-mode enforce step fails on EXIT == 2)
- agent-redline Check Run conclusion: `failure` (🔴 red X in the commit list — signals a hard fail distinct from the orange `action_required` for warnings)
- Run-summary visible on the run page; the offending import chain is named precisely
- The push cannot be considered safe to merge until the structure is fixed (or the violation is explicitly baselined via `ignore_imports` in `pyproject.toml`, which is itself a red-zone change).
