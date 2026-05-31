# Policy-change PR

Edits `agent-policy.yaml` itself — specifically, raises the PR-size warn threshold from 20 to 30 changed files.

This demonstrates **governance self-protection**: the policy is the source of truth for what counts as red, blue, and gray everywhere else. If an agent could quietly edit it (drop a red rule blocking its change, raise a threshold past its breach, weaken a checkpoint), every other guard becomes optional. So the policy itself is in the red zone with `architecture-review`.

The chain:

1. The path `agent-policy.yaml` is in the red zone of `agent-policy.yaml` (yes, it lists itself).
2. Touching it produces a `RED` verdict + `architecture-review` checkpoint.
3. The `architecture-reviewed` label satisfies the checkpoint.
4. CI green; the policy change can merge — but only with explicit human signoff.

Without the self-protecting entry, this same diff would land in `gray` and ship without comment. SPEC §7.1 makes the entry mandatory.
