# Push-mode demo: boundary-rule violation

A push that introduces a forbidden import: `orders/domain/order.py` imports `orders/infrastructure/db/in_memory_orders.py`, breaking the "domain stays free of infrastructure" hexagonal contract.

The import-linter contract `Domain stays free of infrastructure` (a `forbidden` contract) fires. The reporter classifies the verdict as BOUNDARY_VIOLATION; CI is red. The verdict appears in the run summary; the developer fixes the structure or reverts the commit.

This is the canonical failure mode the framework is designed to prevent — the agent should refuse to make this change in operating mode, but if the change reaches CI, the boundary backend catches it deterministically. In push-mode the visibility surface is the run-summary page rather than a PR sticky comment.
