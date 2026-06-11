## agent-redline: RED

**1 suppression marker(s) added on guarded surfaces.**

| Zone | Files |
|---|---|
| Red | `src/example/domain/orders.py` |

**Required checkpoints:**
- [ ] `architecture-review` — red-zone change: src/example/domain/orders.py. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary check:** passed

**Suppressions added (1):**

| File | Line | Marker | Zone |
|---|---|---|---|
| `src/example/domain/orders.py` | 11 | `# noqa` | red |

Suppressions on guarded surfaces require `architecture-review`.

[Why this matters](docs/agent/boundary-violation.md#suppressions)

**API check:** no changes
**PR size:** 1 files / 1 lines (ok)
