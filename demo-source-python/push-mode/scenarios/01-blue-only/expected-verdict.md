# Expected verdict (push-mode)

The run summary at the top of github.com/{owner}/{repo}/actions/runs/{id} shows:

```
## agent-redline verdict

## agent-redline: BLUE

**All changes in blue zones.**

| Zone | Files |
|---|---|
| Blue | `tests/test_isolated_helper.py` |

**API check:** no changes
**Change size:** 1 files / N lines (ok)
```

- Verdict: BLUE
- Reporter exit code: 0
- Workflow conclusion: success (green)
- Run-summary visible at the top of the workflow run page on GitHub
- No checkpoints required
- No email notification fires (GitHub only emails on failure by default)
