# Red-zone PR with checkpoint label

Adds a `cancel()` method to the `Order` aggregate that throws if the
order has already shipped. Modifies a domain invariant — red zone,
requires architecture-review.

The PR has the `architecture-reviewed` label applied (or a CODEOWNER
approval), satisfying the checkpoint. CI green; PR can merge.
