# Expected verdict (verified live on agent-redline-python-demo PR #23)

A `# noqa: import-linter` inline comment is added to
`src/orders/domain/repositories/orders_repository.py` (red zone). The PR
adds 2 lines, so size is fine; the only thing the reporter is asserting
on is the suppression marker.

## With the `architecture-reviewed` label

```
## agent-redline: RED

**1 suppression marker(s) added on guarded surfaces.**

| Zone | Files |
|---|---|
| Red | `src/orders/domain/repositories/orders_repository.py` |

**Required checkpoints:**
- [x] `architecture-review` — red-zone change: src/orders/domain/repositories/orders_repository.py. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary check:** passed

**Suppressions added (1):**

| File | Line | Marker | Zone |
|---|---|---|---|
| `src/orders/domain/repositories/orders_repository.py` | 11 | `# noqa` | red |

Suppressions on guarded surfaces require `architecture-review`.

[Why this matters](docs/agent/boundary-violation.md#suppressions)

**API check:** no changes
**PR size:** 1 files / 2 lines (ok)
```

- Verdict: RED
- Reporter exit code: 0 — the only required checkpoint is satisfied via
  the label.
- CI: green (`report` job passes; `boundary` job passes).

## Without the `architecture-reviewed` label

Same comment body, but the checkpoint flips to unsatisfied:

```
**Required checkpoints:**
- [ ] `architecture-review` — red-zone change: ...
```

- Verdict: RED
- Reporter exit code: 2 (binding-mode hard fail) — `Reporter exited 2
  (binding-mode hard fail). Failing the report check.`
- CI: red — `report` job fails; `boundary` job still passes.

This confirms the new suppression-detection feature drives binding-mode
behavior (exit 2) when a suppression marker is added on a red-zone
Python file without the architecture-review checkpoint, and that the
`architecture-reviewed` label flips the checkpoint to satisfied (exit 0,
green CI).
