# Blue-only PR

Adds a small isolated test in `tests/` (a blue zone). No production code touched.

The agent-redline reporter classifies this as BLUE: no checkpoints required, CI green.

This is the canonical happy-path: agents work autonomously in blue zones; reviewers don't need to be woken up for tests.
