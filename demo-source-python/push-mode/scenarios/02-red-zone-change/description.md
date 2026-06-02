# Push-mode demo: red-zone change (no PR-label mechanism)

A push that adds a method to `OrdersRepository` (the domain port). This is a structural change — every adapter must implement the new method, every caller may use it.

The reporter classifies this as RED: the path `src/orders/domain/repositories/**` is in the red zone with checkpoint `architecture-review`. Reporter exits 1 (warnings).

**In push-driven flow, there's no PR-label mechanism to satisfy the checkpoint.** The verdict appears in the run summary; CI is red because the enforce step fails on `EXIT != 0`. The developer sees "this push touched red-zone code — review it" via the run summary, decides whether the change is sound, and (if so) merges/keeps the commit. The signal is informational; the CI red is the visibility channel.

If the team wants to satisfy the checkpoint formally on push-driven flow, two options:

1. **Make the architecture review a separate, paired commit.** The next commit after this one revises the change after review (or adds a doc explaining the architectural intent). Both commits ship together; the first one's CI run still shows red (a historical record), the second one's CI run is clean.

2. **Add a label-equivalent via commit message convention.** Some teams put `[architecture-reviewed]` in the commit message; a custom rule in the policy could parse it. Not yet built into agent-redline; would be a custom checkpoint satisfier.

For this demo: we leave the CI red and let the run summary surface the verdict.
