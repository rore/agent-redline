# Schema-change PR

Adds a new Flyway migration (`V2__add_customer_email_to_orders.sql`) that adds a `customer_email` column to the `orders` table.

This is the canonical demonstration of the **persistence-review checkpoint**:

1. The path `src/main/resources/db/migration/**` is in the red zone with `checkpoint: persistence-review`.
2. The reporter's `schemaChanges.detected` flag fires when any matched migration path is touched.
3. The PR comment shows verdict `SCHEMA_CHANGE` with the `persistence-review` checkpoint required.
4. The PR has the `persistence-reviewed` label applied (or a CODEOWNER approval) satisfying the checkpoint, so the PR can merge.

Migrations are forward-only — once shipped, you can't unship them — so persistence changes deserve a different review cadence than ordinary code changes. agent-redline routes them automatically.
