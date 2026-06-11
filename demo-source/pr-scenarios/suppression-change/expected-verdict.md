# Expected verdict (verified live on agent-redline-demo PR #83)

A `@SuppressWarnings("ArchUnit")` is added to `OrderController` (red zone).
The PR's modify-line count is 1, so size is fine; the only thing the
reporter is asserting on is the suppression marker.

## With the `architecture-reviewed` label

```
## agent-redline: RED

**1 suppression marker(s) added on guarded surfaces.**

| Zone | Files |
|---|---|
| Red | `src/main/java/com/example/orders/controller/OrderController.java` |

**Required checkpoints:**
- [ ] `api-review` — red-zone change: src/main/java/com/example/orders/controller/OrderController.java. Satisfy by: CODEOWNER approval or label `api-reviewed`
- [x] `architecture-review` — Suppression marker on guarded surface: @SuppressWarnings at src/main/java/com/example/orders/controller/OrderController.java:22. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary check:** passed

**Suppressions added (1):**

| File | Line | Marker | Zone |
|---|---|---|---|
| `src/main/java/com/example/orders/controller/OrderController.java` | 22 | `@SuppressWarnings` | red |

Suppressions on guarded surfaces require `architecture-review`.

[Why this matters](docs/agent/boundary-violation.md#suppressions)

**API check:** no changes
**PR size:** 1 files / 1 lines (ok)
```

- Verdict: RED
- Reporter exit code: 1 (warn) — the controller is also covered by an
  `api-review` red-zone rule, which stays unsatisfied because the PR
  doesn't carry `api-reviewed`. The suppression-driven
  `architecture-review` checkpoint does flip to `[x]`.
- CI: green (`Reporter exited 1 — non-blocking` under shadow mode).

## Without the `architecture-reviewed` label

Same comment body, but both checkpoints unsatisfied:

```
**Required checkpoints:**
- [ ] `api-review` — red-zone change: ...
- [ ] `architecture-review` — Suppression marker on guarded surface: ...
```

- Verdict: RED
- Reporter exit code: 2 (binding-mode hard fail) — `Reporter exited 2
  (binding-mode hard fail). Failing the report check.`
- CI: red — `report` job fails; `archunit` and `generate-specs` still pass.

This confirms the new suppression-detection feature drives binding-mode
behavior (exit 2) when suppressions on guarded surfaces are introduced
without the architecture-review checkpoint, and that the
`architecture-reviewed` label flips the suppression-driven checkpoint
to satisfied (downgrading the failure to warn under shadow mode).
