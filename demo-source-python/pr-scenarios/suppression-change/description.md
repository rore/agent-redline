# Suppression marker added on a guarded surface

This PR adds a `# noqa: import-linter` line to the `OrdersRepository`
port (the domain repository interface). The reporter detects the added
suppression on a red-zone file and routes the PR to architecture-review.

Demonstrates the suppression-detection feature.
