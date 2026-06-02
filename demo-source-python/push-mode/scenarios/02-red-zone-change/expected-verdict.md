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
- Reporter exit code: 1 (unsatisfied checkpoint surfaces as warnings; binding hard fail would be exit 2)
- CI: **red** (enforce step fails on EXIT != 0)
- Run-summary visible on the run page
- The "Satisfy by: CODEOWNER approval or label" note is from the policy. **In push-mode there's no PR to label**; the developer sees the warning and either commits a separate review-acknowledgment commit, or merges the policy's red-zone classification.
