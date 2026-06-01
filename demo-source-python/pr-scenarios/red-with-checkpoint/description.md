# Red-zone change with checkpoint

Adds a new method to `OrdersRepository` (the domain port). This is a structural change — every adapter must implement the new method, and every caller may use it.

The reporter classifies this as RED: the path `src/orders/domain/repositories/**` is in the red zone with checkpoint `architecture-review`. The PR is opened with the `architecture-reviewed` label, which satisfies the checkpoint. CI is green.

This is the canonical "structurally consequential change, properly reviewed" path.
