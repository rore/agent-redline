# Expected verdict (push-mode)

The run summary at the top of github.com/{owner}/{repo}/actions/runs/{id} shows:

```
## agent-redline verdict

## agent-redline: RED

**Red-zone files changed.**

| Zone | Files |
|---|---|
| Red | `src/orders/domain/repositories/orders_repository.py` |
| Watch | `src/orders/infrastructure/db/in_memory_orders.py` |

**Required checkpoints:**
- [ ] `architecture-review` — red-zone change: src/orders/domain/repositories/orders_repository.py. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary check:** passed
**API check:** no changes
**PR size:** 2 files / ~12 lines (ok)
```

- Verdict: RED
- Reporter exit code: 1
- Workflow job: **green** (push-mode fails the workflow only on EXIT == 2)
- agent-redline Check Run conclusion: `action_required` (🟠 orange warning in the commit list — distinct from a red failure; surfaces on the commit list and triggers GitHub notifications without blocking unrelated jobs)
- Run-summary visible on the run page
- The "Satisfy by: CODEOWNER approval or label" note is from the policy. **In push-mode there's no PR to label**; the developer sees the orange icon on the commit, opens the run summary, and acknowledges by reviewing the change in place. The signal is delivered; there is no flag to flip.
