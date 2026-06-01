# PR scenarios

Each subdirectory describes one of the three planned PR branches in `agent-redline-python-demo`. Each scenario has:

- `branch.txt` — the branch name
- `description.md` — what the PR demonstrates
- `expected-verdict.md` — what the agent-redline reporter should produce
- `apply.sh` — script that, run from inside a checkout of the demo repo at `main`, mutates the worktree to produce the scenario's diff

`scripts/sync-python-demo.sh --with-pr-branches` runs the apply scripts to produce the three branches.

## The three scenarios

| Scenario | Branch | Verdict |
|---|---|---|
| Blue-only test add | `demo/blue-only-pr` | `BLUE`, exit 0 |
| Red-zone change with checkpoint label | `demo/red-with-checkpoint-pr` | `RED`, exit 0 (checkpoint satisfied via label) |
| Boundary-rule violation | `demo/boundary-violation-pr` | `BOUNDARY_VIOLATION`, exit 2 |

Together they cover the three PR-side outcomes the framework is designed to make visible.
