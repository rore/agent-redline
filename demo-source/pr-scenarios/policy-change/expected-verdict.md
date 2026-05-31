# Expected verdict (target state for the demo)

When the `architecture-reviewed` label is applied:

```
## agent-redline: RED

**Red-zone files changed.**

| Zone | Files |
|---|---|
| Red | `agent-policy.yaml` |

**Required checkpoints:**
- [x] `architecture-review` — red-zone change: agent-policy.yaml. Satisfy by: CODEOWNER approval or label `architecture-reviewed`

**Boundary check:** passed
**API check:** no changes
**PR size:** 1 files / 2 lines (ok)
```

- Verdict: `RED`
- Exit code: 0 (checkpoint satisfied via the label)
- CI: `archunit` green, `generate-specs` green, `report` green

If the label is removed, the checkpoint flips to `[ ]` (unsatisfied) and the report's exit code becomes 1 (warn) under shadow mode. Under binding mode, the policy edit would be merge-blocked.

The interesting bit: the change itself is trivial — a 2-line tweak to a threshold — but `agent-policy.yaml` is the source of truth for governance. Without `agent-policy.yaml` declared red in `agent-policy.yaml` (yes, the policy lists itself), this same diff would land in `gray` and ship without checkpoint. The self-listing is what makes governance self-protecting.

Without this entry, an agent could edit the policy to remove the rule blocking its current change and ship the change unchallenged. SPEC §7.1 makes the entry mandatory; bootstrap-mode hard rule #7 enforces it at generation time.
