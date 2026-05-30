# Boundary-rule violation PR

Adds a forbidden import: `OrderService` (in `application/`) imports
`PostgresOrderRepository` (in `adapter/persistence/`) directly,
bypassing the `OrderRepository` port.

The ArchUnit rule `application_must_not_depend_on_persistence_adapters`
fires. CI is red. The PR cannot merge until the structure is fixed.

This is the canonical failure mode the framework is designed to prevent
— the agent should refuse to make this change in operating mode, but if
the change reaches CI, the boundary backend catches it deterministically.
