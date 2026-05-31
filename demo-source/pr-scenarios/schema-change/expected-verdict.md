# Expected verdict (target state for the demo)

When the `persistence-reviewed` label is applied:

```
## agent-redline: SCHEMA_CHANGE

**Persistence schema changed.**

| Zone | Files |
|---|---|
| Red | `src/main/resources/db/migration/V2__add_customer_email_to_orders.sql` |

**Required checkpoints:**
- [x] `persistence-review` — red-zone change: src/main/resources/db/migration/V2__add_customer_email_to_orders.sql. Satisfy by: CODEOWNER approval or label `persistence-reviewed`

**Boundary check:** passed
**API check:** no changes
**Schema check:** changes detected
**PR size:** 1 files / ~7 lines (ok)
```

- Verdict: `SCHEMA_CHANGE`
- Exit code: 0 (checkpoint satisfied via the label)
- CI: `archunit` green, `generate-specs` green, `report` green

If the label is removed, the checkpoint flips to `[ ]` (unsatisfied) and the report's exit code becomes 1 (warn) under shadow mode. Under binding mode the PR would be merge-blocked.

The Schema check section is the value-add: the path-glob match on `src/main/resources/db/migration/**` is what triggers `schemaChanges.detected`. Both the path classification (red zone) and the schema-detection flag fire together for migration touches.
