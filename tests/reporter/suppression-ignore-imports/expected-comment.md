## agent-redline: RED

**1 suppression marker(s) added on guarded surfaces.**

| Zone | Files |
|---|---|
| Red | `pyproject.toml` |

**Required checkpoints:**
- [ ] `architecture-review` — red-zone change: pyproject.toml. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary check:** passed

**Suppressions added (1):**

| File | Line | Marker | Zone |
|---|---|---|---|
| `pyproject.toml` | 21 | `ignore_imports` | red |

Suppressions on guarded surfaces require `architecture-review`.

[Why this matters](docs/agent/boundary-violation.md#suppressions)

**API check:** no changes
**PR size:** 1 files / 1 lines (ok)
