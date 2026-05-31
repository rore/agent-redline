# Expected verdict (target state for the demo)

```
## agent-redline: BLUE

**All changes in blue zones.**

| Zone | Files |
|---|---|
| Blue | `src/test/java/com/example/orders/oversized/Filler01Test.java`, ... (+59 more) |

**Boundary check:** passed
**API check:** no changes
**PR size:** 60 files / ~720 lines (fail)
```

- Headline verdict: `BLUE` — every file is in the blue zone (`src/test/**`).
- Exit code: `2` — `pr_size: binding` in `modes.perCheck` makes the size-fail breach a hard fail, even though the headline classification is blue.
- CI: `archunit` green, `generate-specs` green, `report` **red**. `report` is a required status check, so branch protection blocks merge.
- Recommended action: `split-pr`.

The interesting bit: the *zone* classification is BLUE (no contracts touched, no architecture, no security), but the PR is still merge-blocked because of size alone. That's the point — even unambiguously safe code becomes risky at PR-size 60. Reviewers who try to read the diff will skim, miss things, or rubber-stamp.

If `modes.perCheck.pr_size` were `shadow` (the default for size in most adopters' first weeks), the reporter would still emit `(fail)` in the comment but exit 1 (warning) instead of 2, and branch protection wouldn't block. The demo runs `binding` to demonstrate the gate end-to-end.

There's no label that satisfies the size guard. The fix is to split the PR, not approve around it.
