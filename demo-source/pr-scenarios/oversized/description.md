# Oversized PR

Adds 60 trivial test files to demonstrate the **PR-size guard**:

- `agent-policy.yaml` declares `prRules.maxChangedFiles.fail: 50`.
- `agent-policy.yaml` declares `modes.perCheck.pr_size: binding`.
- This PR touches 60 files, breaching the fail threshold.
- The reporter emits exit code `2` and the `report` check fails.
- Branch protection blocks merge.

The files are all in the blue zone (`src/test/**`), so the only thing breached is size. This isolates the size signal from any other checkpoint or boundary concern.

Why this matters: a PR that exceeds reasonable human attention is approved blindly. agent-redline includes deterministic size limits because no amount of reviewer discipline scales past a certain diff. The point of binding mode here is the **gate**, not the warning — once a team has tuned its threshold, oversized PRs should be impossible to merge.

This scenario can be unblocked by splitting the PR (the canonical fix), not by raising the threshold.
