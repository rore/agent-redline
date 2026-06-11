# Suppression marker added on a guarded surface

This PR adds `@SuppressWarnings("ArchUnit")` on `OrderController.java` to
silence a hypothetical ArchUnit failure. The reporter detects the added
suppression and routes the PR to architecture-review.

Demonstrates the suppression-detection feature.
