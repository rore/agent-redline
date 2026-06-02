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
- [ ] `architecture-review` — red-zone change: src/orders/domain/repositories/orders_repository.py. Action: review the commit; revert if unintended, otherwise the red CI run on this commit is the audit record.

**Boundary check:** passed
**API check:** no changes
**Change size:** 2 files / ~12 lines (ok)
```

- Verdict: RED
- Reporter exit code: 1
- Workflow conclusion: **failure** — agent-redline workflow itself is red. Other workflows in the repo (tests, builds) run independently and are not affected.
- GitHub's default email-on-failure notification fires for the user who pushed the commit. The email links to the run page where the verdict is rendered above.
- The red badge on this commit's agent-redline run is the audit trail that this change required human review. No "approve" mechanism exists in push-mode (and isn't needed) — the next push that touches no red zone produces a green agent-redline run going forward.
- Push-mode checkpoint text reads as a review obligation on the commit. CODEOWNER approval / `architecture-reviewed` label phrasing is intentionally omitted because neither mechanism exists on a direct push (no PR to label, no CODEOWNER review request).
