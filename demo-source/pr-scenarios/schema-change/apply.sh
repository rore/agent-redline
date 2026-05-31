#!/usr/bin/env bash
# pr-scenarios/schema-change/apply.sh
#
# Mutates a clean main checkout to add a Flyway migration that introduces
# a new column on the orders table. This produces a real
# src/main/resources/db/migration/** touch that the reporter classifies
# as SCHEMA_CHANGE + persistence-review.

set -euo pipefail

MIGRATION_DIR="src/main/resources/db/migration"
MIGRATION_FILE="$MIGRATION_DIR/V2__add_customer_email_to_orders.sql"

[[ -d "$MIGRATION_DIR" ]] || { echo "error: $MIGRATION_DIR not found" >&2; exit 1; }

if [[ -f "$MIGRATION_FILE" ]]; then
    echo "$MIGRATION_FILE already present; nothing to apply"
    exit 0
fi

cat > "$MIGRATION_FILE" <<'EOF'
-- Add a customer_email column to support customer notifications on
-- order events. Nullable to keep V1 rows valid without backfill;
-- application logic enforces presence on new orders.
ALTER TABLE orders
    ADD COLUMN customer_email VARCHAR(320);

CREATE INDEX idx_orders_customer_email ON orders(customer_email);
EOF

echo "added $MIGRATION_FILE"
