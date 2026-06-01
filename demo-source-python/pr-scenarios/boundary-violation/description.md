# Boundary-rule violation PR

Adds a forbidden import: `orders/domain/order.py` imports from `orders/infrastructure/db/in_memory_orders.py`, breaking the "domain stays free of infrastructure" hexagonal boundary.

The import-linter contract `Domain stays free of infrastructure` (a `forbidden` contract) fires. The agent-redline reporter classifies the verdict as BOUNDARY_VIOLATION. CI is red. The PR cannot merge until the structure is fixed.

This is the canonical failure mode the framework is designed to prevent — the agent should refuse to make this change in operating mode, but if the change reaches CI, the boundary backend catches it deterministically.
