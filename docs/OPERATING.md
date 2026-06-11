# Operating mode

Operating mode is what the skill describes for any work in a repo that contains `agent-policy.yaml`. It applies whenever the skill is loaded in such a repo. (How the skill gets loaded — automatic on session start, explicit invocation, or harness-specific triggers — depends on the harness.)

## Activation

The skill checks for `agent-policy.yaml` in the repo root. If present, operating-mode guidance applies. If absent, the skill is dormant.

## The operating loop

```
1. Read agent-policy.yaml.
2. Classify the intended change BEFORE editing.
3. Branch by classification.
4. Edit (or escalate).
5. Run the local check.
6. Write a PR description that exposes the classification.
```

Every step matters. Skipping classification before editing is the most common failure mode and the most damaging — it's how shortcuts ship.

## Step 1 — Read the policy

The agent reads `agent-policy.yaml` and forms a working model of:

- Which paths are red, blue, watch (and which fall through to gray)
- Which boundary rules apply
- Where the API surface lives
- Where persistence lives
- Where security lives
- What checkpoints exist and how they're satisfied

## Step 2 — Classify

Before any edit, the agent answers:

- Which files would I change?
- What zone do they fall in?
- Do any boundary rules apply to dependencies I'd add or modify?
- Am I touching API, schema, security, or runtime config?

The classification is one of:

| Classification | Meaning |
|---|---|
| `BLUE` | All touched files are blue. Proceed with normal autonomy. |
| `RED` | At least one touched file is red. Stop. Plan a checkpoint. |
| `GRAY` | At least one touched file is gray (no zone matched). Proceed cautiously; surface in PR; suggest the path be classified. |
| `BOUNDARY_RISK` | The intended change would create a forbidden dependency. Do not proceed. |
| `API_CHANGE` | Touched API contract surface. Requires `api-review`. |
| `SCHEMA_CHANGE` | Touched migration or persistence model. Requires `persistence-review`. |
| `SECURITY_CHANGE` | Touched security/auth code. Requires `security-review`. |
| `CONFIG_CHANGE` | Touched a runtime-config path. Requires `ops-review` (or whichever `runtimeConfig.checkpoint` the policy declares). |
| `MIXED` | Combination of the above. Resolve to the most-restrictive applicable. |

The `watch` list is a separate, additive concern — independent of the classification above. A file can be `red+watch`, `blue+watch`, or `gray+watch`. Watch on its own never produces a verdict, but each watched-and-changed file gets a row in the PR comment so the reviewer sees it. Mention any `watch` files in your PR description briefly: "Touched `*Configuration.java`; affects bean wiring globally; verified beans still resolve."

## Step 3 — Branch by classification

### Blue

Proceed. Edit normally. The skill stays out of the way.

### Red

Stop before editing.

Produce a short **checkpoint note**:

```
## Checkpoint: architecture-review

What is changing: <one or two sentences>
Why: <reason>
Affected contract / model / boundary: <which one>
Compatibility / migration risk: <low | medium | high, with one-line reason>
Verification plan: <tests, checks, manual validation>
```

If the developer has already authorized the red-zone change explicitly (e.g., the task description says "extend the OrderRepository port to support X"), proceed and include the checkpoint note in the PR description.

If the developer's request is ambiguous, ask before editing.

### Gray

Proceed cautiously. Surface in the PR description that the change touched gray-zone code, and suggest the path be classified explicitly going forward.

### Boundary risk

The intended change would create a forbidden dependency.

**Do not work around the rule.** Specifically:

- Do not add `@SuppressWarnings` or equivalent
- Do not modify the boundary-rule backend definition (an ArchUnit test, a dependency-cruiser config, a Semgrep rule, etc.) to allow the dependency
- Do not add a new transitive layer to launder the import

Either:

1. **Fix the structure.** Open the port, extend the interface, introduce the abstraction. This may itself be a red-zone change requiring an `architecture-review` checkpoint.
2. **Escalate.** Tell the developer the change requires a modeling decision they should make explicitly.

The skill must refuse to ship a boundary-violating PR. Without this, every other rule is gameable: the easy local shortcut becomes the path of least resistance and the system stops working.

### Suppression markers

Adding a suppression marker on a guarded surface — `# noqa`, `# type: ignore`, `@SuppressWarnings`, `@SuppressFBWarnings`, `@ArchIgnore`, `ignore_imports`, `per-file-ignores`, or any other marker listed in `.agent-redline/suppressions.yaml` — is the same shape of shortcut as a boundary workaround, regardless of whether the touched path is red, blue, or gray. The agent must not silence the check.

Either:

1. **Fix the structure** so the marker isn't needed (extract the unused import, narrow the type, open the port). The fix may itself be red-zone.
2. **Escalate.** If the suppression is genuinely warranted (third-party API quirk, generated code, an exempt-path-worthy surface that the policy doesn't yet exempt), surface it to the developer and let them decide whether to extend `suppressions.exemptPaths` — that policy edit is itself red-zone.

The reporter scans added lines independently. Even if the agent slips a marker through, CI's suppression scan surfaces it as a `Suppressions` row in the PR comment and routes the change to `architecture-review`. Detection is opt-in per policy (`suppressions:` block); see [`docs/superpowers/specs/2026-06-10-suppression-detection-design.md`](superpowers/specs/2026-06-10-suppression-detection-design.md) and the corresponding entry in [`DECISIONS.md`](DECISIONS.md) for the rationale and the marker lists.

### API / schema / security change

Treat as red. Produce the appropriate checkpoint note. Verify the developer has authorized the contract change before proceeding.

## Step 4 — Edit

Implement the change, staying within the classification's discipline.

- Keep edits scoped to what was classified
- Don't expand into other zones during implementation; if you need to, re-classify
- Don't add unrelated cleanup; small PRs

## Step 5 — Local check

Run `scripts/agent-redline-check.sh`. This runs the same reporter CI runs, against the local diff. It will:

- Report the verdict
- Surface any boundary violations
- Surface any required checkpoints
- Report PR size

If the local check reports problems, fix them before declaring work done.

## Step 6 — Change description

Write a description that exposes the classification. The description goes:
- in the **PR description** for PR-driven flow (use the repo's PR template; bootstrap added the relevant fields), or
- in the **commit message** for push-driven flow (no PR exists; the commit message is the only durable record per change).

Either way, write:

- The classification (red / blue / gray; any watch paths touched)
- Which checkpoint the change satisfies, if any
- A *short, factual* "what changed" — not a history of attempts, not a restatement of requirements, not a paragraph per file
- A *short* "why"
- The verification commands actually run

Do not produce verbose generated descriptions. The reporter may flag them as slop.

## What operating mode does NOT do

- Does not run agents in shadow on every keystroke. Classification happens at the start of a logical change, not continuously.
- Does not enforce style or correctness. That's tests and linters.
- Does not approve its own PRs. CI does the deterministic check; humans handle checkpoints.
- Does not modify `agent-policy.yaml` to make a difficult change easier. Policy changes are themselves red-zone.

## Behavior in legacy / messy repos

If the agent finds `agent-policy.yaml` but the policy is clearly out of sync with the actual codebase (zones reference paths that no longer exist; boundary rules point at packages that have moved), the agent should:

1. Flag the inconsistency
2. Treat the affected paths as gray until the policy is fixed
3. Suggest a policy-update task as a separate red-zone change

Do not silently ignore the policy. Do not silently update the policy mid-task.

## When in doubt

If classification is ambiguous, default to the more conservative outcome. Gray > blue. Red > gray. Boundary-risk > everything.

The cost of a false-red is a 30-second checkpoint conversation. The cost of a false-blue is structural debt the next agent inherits. The asymmetry is severe; bias accordingly.
